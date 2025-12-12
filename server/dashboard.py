from flask import Flask, send_from_directory, request
import subprocess, json, psutil, os

cfg = json.load(open("config.json"))
GW_PORT = cfg["port"]
DASH_PORT = GW_PORT + 1

app = Flask(__name__, static_folder="static")

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/api/status")
def status():
    return {
        "service": subprocess.getoutput("systemctl is-active llm-gateway.service"),
        "cpu": psutil.cpu_percent(),
        "memory": psutil.virtual_memory().percent,
        "proxy_mode": cfg["proxy_mode"],
        "port": GW_PORT
    }

@app.route("/api/logs")
def logs():
    logs = subprocess.getoutput("journalctl -u llm-gateway.service -n 50 --no-pager")
    return {"logs": logs}

@app.route("/api/control", methods=["POST"])
def control():
    action = request.json.get("action")
    if action not in ["start", "stop", "restart"]:
        return {"error": "invalid command"}
    os.system(f"sudo systemctl {action} llm-gateway.service")
    return {"ok": True}

@app.route("/api/config", methods=["POST"])
def update_config():
    new_cfg = request.json
    cfg.update(new_cfg)
    json.dump(cfg, open("config.json", "w"), indent=4)
    return {"updated": True}

app.run(host="0.0.0.0", port=DASH_PORT)