from flask import Flask, request, jsonify
import requests, json

# Load config
cfg = json.load(open("config.json"))
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
    if API_KEY and request.headers.get("X-API-Key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    resp = session.post(f"{OLLAMA_URL}/api/generate", json=data)
    return resp.text, resp.status_code, {"Content-Type": "application/json"}

@app.route("/health")
def health():
    return {"ok": True}

app.run(host="0.0.0.0", port=PORT)