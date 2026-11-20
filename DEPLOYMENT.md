# DEPLOYMENT GUIDE — Delta AI Trading Platform

## 1. Overview
The **Delta AI Trading Platform** is an enterprise-grade multi-agent autonomous algorithmic trading system built for **Delta Exchange India**. It includes a 12-page dark-mode operations dashboard, real-time market scanner, 7-agent consensus committee (with an independent Skeptic veto), deterministic risk engine, paper trading simulator, and persistent SQLite database.

---

## 2. Server Prerequisites
- **Operating System:** Linux (Ubuntu/Debian) or Windows Server
- **Python Version:** Python 3.10+ (Recommended: Python 3.11 or 3.12)
- **Containerization (Optional):** Docker & Docker Compose
- **Network Access:** Outbound HTTPS to `https://api.india.delta.exchange`

---

## 3. Environment Variables (`.env`)
Create a `.env` file in the platform root directory. The application safely maps these variables without exposing them:

```ini
# Delta Exchange India Credentials (Already active on your server)
DELTA_INDIA_API_KEY=your_delta_api_key_here
DELTA_INDIA_API_SECRET=your_delta_api_secret_here
DELTA_INDIA_BASE_URL=https://api.india.delta.exchange
DELTA_ENV=production

# Server Port
PORT=8090

# Optional Telegram Notifications
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

---

## 4. Local / Server Native Run

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Run Application
```bash
python main.py
# Or using uvicorn directly:
uvicorn main:app --host 0.0.0.0 --port 8090
```

### Step 3: Access Web Dashboard
Open your web browser and navigate to:
```
http://YOUR_SERVER_IP:8090
```

---

## 5. Docker Deployment

```bash
docker compose up -d --build
```
Check health:
```bash
curl http://localhost:8090/api/exchange/status
```

---

## 6. Safety & Operational Modes
1. **PAPER TRADING (Default):** All trade proposals, strategy signals, risk calculations, and orders are executed in virtual simulation with fees and slippage calculated. Real money is never placed.
2. **LIVE TRADING:** Requires explicit toggling in the Settings tab (`Page 12`). When enabled, the Trader Agent submits real orders to Delta Exchange India only after achieving unanimous consensus from all 7 agents and the independent Risk Engine.
