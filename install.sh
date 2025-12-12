#!/usr/bin/env bash
set -e

echo "== LLM Gateway Installer =="
INSTALL_DIR="/opt/llm-gateway"

sudo mkdir -p $INSTALL_DIR
sudo cp -r . $INSTALL_DIR
cd $INSTALL_DIR

# 1. CHECK OLLAMA
if ! command -v ollama &> /dev/null
then
    echo "[*] Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
else
    echo "[✓] Ollama already installed."
fi

# 2. ASK FOR PORT
read -p "Enter gateway port (default 3000): " PORT
PORT=${PORT:-3000}

# 3. ASK FOR API KEY
read -p "Enter API key for client access (optional): " API_KEY

# 4. VPN / PROXY
echo "Choose network proxy:"
echo "[1] No proxy"
echo "[2] SOCKS5"
echo "[3] OpenVPN (.ovpn)"
read -p "Choice: " NET_CHOICE

PROXY_MODE="none"
SOCKS_ADDR=""

if [[ "$NET_CHOICE" == "2" ]]; then
    PROXY_MODE="socks5"
    read -p "Enter SOCKS5 address (127.0.0.1:1080): " SOCKS_ADDR
elif [[ "$NET_CHOICE" == "3" ]]; then
    PROXY_MODE="openvpn"
    echo "Place your .ovpn file in:"
    echo "$INSTALL_DIR/server/vpn-config.ovpn"
fi

# Write config
cat <<EOF | sudo tee server/config.json
{
    "port": $PORT,
    "api_key": "$API_KEY",
    "proxy_mode": "$PROXY_MODE",
    "socks_addr": "$SOCKS_ADDR"
}
EOF

echo "[✓] Config saved to server/config.json"

# Install requirements
echo "[*] Installing Python dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip
pip3 install flask requests psutil

echo "[*] Installing systemd services..."

# Copy service units
if [ -d "/etc/systemd/system" ]; then
    sudo cp systemd/llm-gateway.service /etc/systemd/system/
    sudo cp systemd/llm-dashboard.service /etc/systemd/system/
else
    echo "[!] /etc/systemd/system not found. Skipping service installation."
fi

# Only attempt to enable/start services if systemd is the init system
if pid1_name=$(ps -p 1 -o comm= 2>/dev/null) && [ "$pid1_name" = "systemd" ]; then
    echo "[✓] Systemd detected (PID 1 = systemd)."
    sudo systemctl daemon-reload
    sudo systemctl enable --now llm-gateway.service || true
    sudo systemctl enable --now llm-dashboard.service || true

    echo "[*] Service status (brief):"
    sudo systemctl status llm-gateway.service --no-pager || true
    sudo systemctl status llm-dashboard.service --no-pager || true
else
    echo "[!] No systemd init system detected (PID 1 = ${pid1_name:-unknown})."
    echo "[!] You may be in a container or a system without systemd."
    echo "[!] The service files were copied to /etc/systemd/system, but systemctl cannot manage services here."
    echo "[!] If you are on a host with systemd, run this installer on the host, not inside a container." 
    echo "[!] Alternatively, to run the servers manually, start them with:"
    echo "    sudo python3 /opt/llm-gateway/server/gateway.py &"
    echo "    sudo python3 /opt/llm-gateway/server/dashboard.py &"
fi

echo "-----------------------------------"
echo " LLM Gateway Installed Successfully "
echo "-----------------------------------"
echo "Gateway API:   http://localhost:$PORT"
echo "Dashboard UI:  http://localhost:$((PORT+1))"
echo "Manage:"
echo "  sudo systemctl status llm-gateway.service"
echo "  sudo systemctl status llm-dashboard.service"
echo "-----------------------------------"