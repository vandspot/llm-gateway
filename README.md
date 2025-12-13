# LLM Gateway

A full local gateway + web dashboard for interacting with Ollama from mobile apps or external devices.

## Features

- Local REST API for LLMs
- Web dashboard (status, logs, control)
- SOCKS5 & OpenVPN support
- Auto-start using systemd
- API key protection
- One-command installer

## Installation

```bash
git clone https://github.com/vandspot/llm-gateway
cd llm-gateway
chmod +x install.sh
sudo ./install.sh