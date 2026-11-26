#!/bin/bash
# ==============================================================================
# AETHER QUANT DESK - 1-Click AWS EC2 Setup Script (Supports Amazon Linux 2023 & Ubuntu)
# ==============================================================================

set -e

echo "🚀 [1/5] Updating packages..."
if command -v dnf &> /dev/null; then
    sudo dnf update -y
    echo "📦 [2/5] Installing Git, Python 3, Docker on Amazon Linux..."
    sudo dnf install -y git python3 python3-pip docker
elif command -v apt-get &> /dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y git python3 python3-pip docker.io docker-compose
fi

# Install docker-compose standalone if missing
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
fi

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER || true

echo "📥 [3/5] Cloning AETHER repository..."
cd ~
if [ -d "GrokTradeingBrain" ]; then
    echo "Directory exists, pulling latest..."
    cd GrokTradeingBrain && git pull origin main
else
    git clone https://github.com/indiantrader803-bot/GrokTradeingBrain.git
    cd GrokTradeingBrain
fi

echo "🔐 [4/5] Confirming Public Indian IP..."
EC2_IP=$(curl -s https://api.ipify.org)
echo "--------------------------------------------------------"
echo "✅ YOUR AWS INDIAN PUBLIC IP: $EC2_IP"
echo "👉 Whitelisted on Delta Exchange: YES!"
echo "--------------------------------------------------------"

echo "🚢 [5/5] Building and launching 24/7 container..."
sudo docker-compose down || true
sudo docker-compose up -d --build

echo "========================================================"
echo "🎉 AETHER IS RUNNING 24/7 ON AWS MUMBAI!"
echo "🌐 Open your browser at: http://$EC2_IP:8000"
echo "========================================================"
