import os
from flask import Flask, request, jsonify, Response, stream_with_context
import requests, json
import logging
import sys
from time import time
import sqlite3
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "gateway.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

log = logging.getLogger("llm-gateway")

# Load config
try:
    with open(CONFIG_PATH, "r") as f:
        cfg = json.load(f)
except Exception as e:
    print(f"[CONFIG ERROR] {e}")
    cfg = {
        "port": 3000,
        "api_key": "",
        "proxy_mode": "none",
        "socks_addr": ""
    }
PORT = cfg["port"]
API_KEY = cfg["api_key"]
PROXY_MODE = cfg["proxy_mode"]
SOCKS_ADDR = cfg["socks_addr"]

OLLAMA_URL = "http://127.0.0.1:11434"

app = Flask(__name__)
session = requests.Session()

# Proxy support
if PROXY_MODE == "socks5":
    session.proxies = {
        "http": f"socks5h://{SOCKS_ADDR}",
        "https": f"socks5h://{SOCKS_ADDR}",
    }

@app.before_request
def log_everything():
    try:
        raw = request.get_data(as_text=True)
    except Exception:
        raw = "<unreadable>"

    log.info(
        f"INCOMING "
        f"ip={request.remote_addr} "
        f"path={request.path} "
        f"content-type={request.content_type} "
        f"len={len(raw)}"
    )
    if request.method != "POST":
        return
    if request.path in ["/ping"]:
        return
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.route("/", methods=["POST"])
def chat():
    start = time()
    data = request.json or {}
    is_stream = data.get("stream", False) is True

    client_ip = request.remote_addr
    model = data.get("model", "unknown")

    if "messages" in data:
        endpoint = "/api/chat"
    elif "prompt" in data:
        endpoint = "/api/generate"
    else:
        log.warning(f"Invalid request from {client_ip}")
        return jsonify({"error": "Invalid request format"}), 400

    log.info(f"REQ from {client_ip} model={model} endpoint={endpoint}")
    
    resp = session.post(
        f"{OLLAMA_URL}{endpoint}",
        json=data,
        stream=is_stream
    )
    duration = round((time() - start) * 1000)

    log.info(f"RESP {resp.status_code} model={model} {duration}ms")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO requests (ip, model, endpoint, status, latency_ms)
        VALUES (?, ?, ?, ?, ?)
    """, (client_ip, model, endpoint, resp.status_code, duration))
    conn.commit()
    conn.close()

    if is_stream:
        def generate():
            for line in resp.iter_lines():
                if line:
                    yield line + b"\n"

        return Response(
            stream_with_context(generate()),
            status=resp.status_code,
            content_type="application/json"
        )
    else:
        return resp.text, resp.status_code, {"Content-Type": "application/json"}

@app.route("/api/requests")
def api_requests():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("""
        SELECT
            ts as time,
            ip,
            model,
            status,
            latency_ms as latency
        FROM requests
        ORDER BY id DESC
        LIMIT 100
    """)

    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    return jsonify({"rows": rows})

    
@app.route("/ping",methods=["GET","POST"])
def ping():
    return {"pong": True}

@app.route("/notifications", methods=["GET"])
def get_notifications():
    log.info("=== NOTIFICATIONS ENDPOINT CALLED ===")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    last_check = request.headers.get("Last-Check")
    log.info(f"Last-Check header value: '{last_check}'")

    if last_check:
        log.info(f"Processing Last-Check: {last_check}")
        try:
            last_dt = datetime.fromisoformat(last_check)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            else:
                last_dt = last_dt.astimezone(timezone.utc)

            # Changed from > to >= to include notifications at exact timestamp
            formatted_time = last_dt.strftime("%Y-%m-%d %H:%M:%S")
            log.info(f"DEBUG: Querying notifications WHERE ts >= '{formatted_time}'")
            log.info(f"DEBUG: Original Last-Check header: {last_check}")
            log.info(f"DEBUG: Parsed datetime: {last_dt}")
            
            c.execute("""
                SELECT id, from_user, to_user, title, message, ts
                FROM notifications
                WHERE datetime(ts) >= datetime(?)
                ORDER BY ts ASC
            """, (formatted_time,))

        except Exception as e:
            log.error(f"Last-Check parse failed: {e}")
            c.execute("""
                SELECT id, from_user, to_user, title, message, ts
                FROM notifications
                ORDER BY ts ASC
            """)
    else:
        log.info("No Last-Check header, returning all notifications")
        c.execute("""
            SELECT id, from_user, to_user, title, message, ts
            FROM notifications
            ORDER BY ts ASC
        """)

    rows = c.fetchall()
    log.info(f"DEBUG: Found {len(rows)} notifications")
    if rows:
        log.info(f"DEBUG: First row: {rows[0]}")
    conn.close()

    notifications_list = [
        {
            "id": r[0],
            "from": r[1],
            "to": r[2],
            "title": r[3],
            "message": r[4],
            "timestamp": r[5],
        }
        for r in rows
    ]
    
    log.info(f"DEBUG: Built {len(notifications_list)} notification objects")
    if notifications_list:
        log.info(f"DEBUG: First notification object: {notifications_list[0]}")

    return {
        "notifications": notifications_list,
        "server_time": datetime.now(timezone.utc).isoformat()
    }


@app.route("/notifications/send", methods=["POST"])
def send_notification():
    data = request.json or {}

    title = data.get("title")
    message = data.get("message")
    from_user = data.get("from")
    to_user = data.get("to")

    if not title or not message:
        return jsonify({"error": "Missing required fields"}), 400

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (from_user, to_user, title, message)
        VALUES (?, ?, ?, ?)
    """, (from_user, to_user, title, message))
    conn.commit()
    notif_id = c.lastrowid
    conn.close()

    log.info(f"NOTIF #{notif_id} {title}")

    return {
        "ok": True,
        "id": notif_id
    }



def init_db():
    log.info(f"Initializing DB at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP,
            ip TEXT,
            model TEXT,
            endpoint TEXT,
            status INTEGER,
            latency_ms INTEGER
        )
    """)
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user TEXT,
            to_user TEXT,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP,
            delivered INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()

init_db()


app.run(host="0.0.0.0", port=PORT)
