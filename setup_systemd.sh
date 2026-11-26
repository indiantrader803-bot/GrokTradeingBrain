#!/bin/bash
# ==============================================================================
# AETHER QUANT DESK - 24/7 Background Systemd Service Launcher
# ==============================================================================

set -e

echo "🚀 [1/3] Setting up Python virtual environment..."
cd ~/GrokTradeingBrain

python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "⚙️ [2/3] Configuring 24/7 background systemd daemon..."
SERVICE_FILE="/etc/systemd/system/aether.service"

sudo bash -c "cat > $SERVICE_FILE" <<EOF
[Unit]
Description=AETHER 24/7 Trading Desk
After=network.target

[Service]
User=$USER
WorkingDirectory=$HOME/GrokTradeingBrain
ExecStart=$HOME/GrokTradeingBrain/venv/bin/python -m app.main
Restart=always
RestartSec=5
Environment=PORT=8000
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

echo "🔄 [3/3] Reloading and starting AETHER service..."
sudo systemctl daemon-reload
sudo systemctl enable aether
sudo systemctl restart aether

EC2_IP=$(curl -s https://api.ipify.org)
echo "========================================================"
echo "🎉 AETHER IS NOW RUNNING 24/7 AS A BACKGROUND SERVICE!"
echo "🌐 Open your browser at: http://$EC2_IP:8000"
echo "========================================================"
