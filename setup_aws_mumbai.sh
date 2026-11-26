#!/bin/bash
# ==============================================================================
# GrokTradingBrain - 1-Click AWS EC2 Mumbai (ap-south-1) Setup Script
# Run this script on your fresh AWS EC2 Ubuntu instance
# ==============================================================================

set -e

echo "🚀 [1/5] Updating system packages..."
sudo apt-get update -y && sudo apt-get upgrade -y

echo "📦 [2/5] Installing Git, Python 3, Docker & Docker Compose..."
sudo apt-get install -y git python3 python3-pip python3-venv docker.io docker-compose

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

echo "📥 [3/5] Cloning GrokTradingBrain repository..."
cd ~
if [ -d "GrokTradeingBrain" ]; then
    echo "Directory exists, pulling latest..."
    cd GrokTradeingBrain && git pull origin main
else
    git clone https://github.com/indiantrader803-bot/GrokTradeingBrain.git
    cd GrokTradeingBrain
fi

echo "🔐 [4/5] Checking Public IP..."
EC2_IP=$(curl -s https://api.ipify.org)
echo "--------------------------------------------------------"
echo "✅ YOUR AWS INDIAN PUBLIC IP: $EC2_IP"
echo "👉 Add this IP ($EC2_IP) to your Delta Exchange API Whitelist!"
echo "--------------------------------------------------------"

echo "🚢 [5/5] Building and launching 24/7 Docker container..."
sudo docker-compose down || true
sudo docker-compose up -d --build

echo "========================================================"
echo "🎉 DEPLOYMENT COMPLETE & RUNNING 24/7!"
echo "🌐 Open your browser at: http://$EC2_IP:8000"
echo "========================================================"
