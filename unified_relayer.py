"""
Continuous 24/7 Unified Exchange Relayer (Delta Exchange India + Binance Futures)
--------------------------------------------------------------------------------
Runs continuously from your machine (India IP: 45.251.233.150).
Both Delta Exchange India and Binance allow access from this IP without cloud blocks.
This service queries live balances and open positions from both exchanges every 4 seconds,
and syncs them to Railway so your dashboard shows 100% genuine real-time data 24/7.
"""

import time
import hmac
import hashlib
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("UnifiedRelayer")

# Delta Exchange India Credentials
DELTA_KEY = "TXkS5Zk9gPlPXGDH7XJtyoxyvLyK9R"
DELTA_SEC = "d38xS6NgMWaZlusaVYpoYTaNYcpzaZuhICmzDLRYwlhWKRO9FcrX7O08HpA2"
DELTA_BASE = "https://api.india.delta.exchange"

# Binance Futures Credentials
BINANCE_KEY = "HJ0uRZiwpPbEYbE8NKxkSXN9V91GKS9kO8i7ntYO1DJtk65IV4oVgTNFqf4mgzTL"
BINANCE_SEC = "5CJYROB9QIYx6b5sQvSeYpfAnqbqpR1YWpAZSOWdiKLaHOV3q7FBNadpgDvCpTFr"

RAILWAY_URL = "https://groktradeingbrain-production.up.railway.app"

def get_delta_data():
    try:
        ts = str(int(time.time()))
        # 1. Balances
        bal_path = "/v2/wallet/balances"
        sig_bal = hmac.new(DELTA_SEC.encode("utf-8"), ("GET" + ts + bal_path).encode("utf-8"), hashlib.sha256).hexdigest()
        headers_bal = {"api-key": DELTA_KEY, "signature": sig_bal, "timestamp": ts, "Content-Type": "application/json"}
        r_bal = requests.get(DELTA_BASE + bal_path, headers=headers_bal, timeout=5)
        
        net_equity = 0.0
        avail_cash = 0.0
        wallets = {}
        if r_bal.status_code == 200:
            d_bal = r_bal.json()
            net_equity = float(d_bal.get("meta", {}).get("net_equity", 0.0) or 0.0)
            for item in d_bal.get("result", []):
                sym = item.get("asset_symbol")
                bal = float(item.get("balance", 0) or 0)
                avail = float(item.get("available_balance", 0) or 0)
                if bal > 0 or avail > 0:
                    wallets[sym] = {"balance": bal, "available": avail, "inr": float(item.get("balance_inr", 0) or 0)}
                    if sym in ["USD", "USDT"]:
                        avail_cash += avail

        # 2. Open Positions
        pos_path = "/v2/positions/margined"
        sig_pos = hmac.new(DELTA_SEC.encode("utf-8"), ("GET" + ts + pos_path).encode("utf-8"), hashlib.sha256).hexdigest()
        headers_pos = {"api-key": DELTA_KEY, "signature": sig_pos, "timestamp": ts, "Content-Type": "application/json"}
        r_pos = requests.get(DELTA_BASE + pos_path, headers=headers_pos, timeout=5)
        
        positions = []
        if r_pos.status_code == 200:
            d_pos = r_pos.json()
            for p in d_pos.get("result", []):
                p_size = float(p.get("size", 0) or 0)
                if p_size != 0:
                    positions.append({
                        "symbol": p.get("product_symbol", "UNKNOWN"),
                        "side": "BUY" if p_size > 0 else "SELL",
                        "size": abs(p_size),
                        "entry_price": float(p.get("entry_price", 0) or 0),
                        "mark_price": float(p.get("mark_price", 0) or 0),
                        "margin": float(p.get("margin", 0) or 0),
                        "unrealized_pnl": float(p.get("unrealized_pnl", 0) or 0)
                    })

        return {
            "net_equity": net_equity,
            "available_cash": avail_cash,
            "wallets": wallets,
            "open_positions": positions
        }
    except Exception as e:
        log.error("Delta query error: %s", e)
        return None

def get_binance_data():
    try:
        timestamp = int(time.time() * 1000)
        query = f"timestamp={timestamp}"
        signature = hmac.new(BINANCE_SEC.encode("utf-8"), query.encode("utf-8"), hashlib.sha256).hexdigest()
        headers = {"X-MBX-APIKEY": BINANCE_KEY}

        # 1. Account
        url = f"https://fapi.binance.com/fapi/v2/account?{query}&signature={signature}"
        r = requests.get(url, headers=headers, timeout=5)
        if r.status_code == 200:
            d = r.json()
            eq = float(d.get("totalMarginBalance", 0.0) or d.get("totalWalletBalance", 0.0) or 0.0)
            avail = float(d.get("availableBalance", 0.0) or 0.0)

            # 2. Positions
            pos_url = f"https://fapi.binance.com/fapi/v2/positionRisk?{query}&signature={signature}"
            p_res = requests.get(pos_url, headers=headers, timeout=5)
            positions = []
            if p_res.status_code == 200:
                for p in p_res.json():
                    amt = float(p.get("positionAmt", 0.0) or 0.0)
                    if amt != 0.0:
                        positions.append({
                            "symbol": p.get("symbol"),
                            "side": "BUY" if amt > 0 else "SELL",
                            "size": abs(amt),
                            "entry_price": float(p.get("entryPrice", 0.0) or 0.0),
                            "mark_price": float(p.get("markPrice", 0.0) or 0.0),
                            "unrealized_pnl": round(float(p.get("unRealizedProfit", 0.0) or 0.0), 4),
                            "leverage": float(p.get("leverage", 1.0) or 1.0)
                        })
            return {"net_equity": eq, "available_cash": avail, "open_positions": positions}
    except Exception as e:
        log.error("Binance query error: %s", e)
    return None

def sync_both(delta_data, binance_data):
    exchanges = {}
    if delta_data:
        exchanges["delta"] = delta_data
    if binance_data:
        exchanges["binance"] = binance_data

    payload = {
        "equity": delta_data.get("net_equity", 0.0) if delta_data else 0.0,
        "available_cash": delta_data.get("available_cash", 0.0) if delta_data else 0.0,
        "positions": delta_data.get("open_positions", []) if delta_data else [],
        "exchanges": exchanges
    }

    try:
        r = requests.post(f"{RAILWAY_URL}/api/sync-live-exchange", json=payload, timeout=5)
        if r.status_code == 200:
            log.info("Synced to Railway: Delta $%.2f USD (%d pos) | Binance $%.2f USDT (%d pos)",
                     delta_data.get("net_equity", 0) if delta_data else 0,
                     len(delta_data.get("open_positions", [])) if delta_data else 0,
                     binance_data.get("net_equity", 0) if binance_data else 0,
                     len(binance_data.get("open_positions", [])) if binance_data else 0)
    except Exception as e:
        log.error("Railway sync error: %s", e)

def main():
    log.info("Starting Unified 24/7 Exchange Relayer (Delta + Binance)...")
    while True:
        d = get_delta_data()
        b = get_binance_data()
        if d or b:
            sync_both(d, b)
        time.sleep(4)

if __name__ == "__main__":
    main()
