import os
from flask import Flask, request, jsonify
import requests, json
import logging
import sys
from time import time
import sqlite3

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
def check_api_key():
    if request.path in ["/health"]:
        return
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.route("/api/chat", methods=["POST"])
def chat():
    start = time()
    data = request.json or {}

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

    resp = session.post(f"{OLLAMA_URL}{endpoint}", json=data)
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


@app.route("/health")
def health():
    return {"ok": True}


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
    conn.commit()
    conn.close()

init_db()


app.run(host="0.0.0.0", port=PORT)