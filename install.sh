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

# Install systemd services
echo "[*] Installing systemd services..."

sudo cp systemd/llm-gateway.service /etc/systemd/system/
sudo cp systemd/llm-dashboard.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable llm-gateway.service
sudo systemctl enable llm-dashboard.service

sudo systemctl start llm-gateway.service
sudo systemctl start llm-dashboard.service

echo "-----------------------------------"
echo " LLM Gateway Installed Successfully "
echo "-----------------------------------"
echo "Gateway API:   http://localhost:$PORT"
echo "Dashboard UI:  http://localhost:$((PORT+1))"
echo "Manage:"
echo "  sudo systemctl status llm-gateway.service"
echo "  sudo systemctl status llm-dashboard.service"
echo "-----------------------------------"