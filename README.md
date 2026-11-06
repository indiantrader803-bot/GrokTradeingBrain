# Grok Capital Growth Trading Brain

**Version:** 1.0  
**Type:** Multi-Asset Autonomous Trading Core + Web Dashboard  
**Designed for:** Desktop + Mobile Browser access  
**Mode:** Demo (default) → Real (after you integrate exchange APIs)

---

## Important Warnings

- This is a **core engine + dashboard**, not a finished commercial product.
- **Never** run with real money until you have thoroughly tested in Demo mode.
- Past performance does not guarantee future results. Most automated systems lose money if risk is not strictly controlled.
- You are fully responsible for API keys, capital, and compliance with your local laws and exchange terms.
- Store API keys securely. Never commit them to Git.

---

## Features

- Fully modular architecture
- Demo / Real mode switch
- Monday–Friday automatic trading
- Weekend trading **only** when strong volume + order flow or high-impact news is detected
- Multi-asset ready (Crypto, Forex, Indices, Metals, Commodities)
- **Supported Exchanges**:
  - Coinbase
  - Delta Exchange India
  - Coinswitch
  - Myfundedperps
  - MetaTrader 5 (MT5)
  - Paper (Demo)
- Smart Platform Router (automatically selects the best exchange for each symbol)
- Strict risk management (position sizing, daily/weekly loss limits, max positions)
- Clean Web Dashboard (works on desktop and mobile browsers)
- Easy to plug in real API keys later

---

## Project Structure

```
GrokTradingBrain/
├── app/
│   └── main.py                 # FastAPI entry point
├── core/
│   ├── config.py
│   ├── risk_manager.py
│   ├── orchestrator.py
│   ├── scheduler.py
│   └── router.py               # Smart multi-exchange router
├── strategies/
│   └── capital_growth.py
├── adapters/
│   ├── base.py
│   ├── paper.py                # Demo / Paper trading
│   ├── coinbase_adapter.py
│   ├── delta_adapter.py
│   ├── coinswitch_adapter.py
│   ├── myfundedperps_adapter.py
│   └── mt5_adapter.py
│   └── example_exchange.py     # Template for real exchanges
├── dashboard/
│   └── templates/
│       └── index.html
├── utils/
│   └── helpers.py
├── data/
├── logs/
├── requirements.txt
└── README.md
```

---

## Quick Start

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   python -m app.main
   ```

3. Open in browser:
   - Desktop: http://localhost:8000
   - Mobile: http://YOUR_SERVER_IP:8000

4. Default mode is **DEMO**.  
   Change to real mode only after integrating your exchange APIs and thorough testing.

---

## How to Add Real Exchanges Later

1. Copy `adapters/example_exchange.py`
2. Implement the required methods (`get_equity`, `get_price`, `place_order`, `close_position`, etc.)
3. Register the adapter in the Orchestrator
4. Switch `mode = "real"` in config only after paper trading results are acceptable

---

## Schedule Logic

- **Monday – Friday**: Normal trading allowed
- **Saturday – Sunday**: Trading allowed **only if**:
  - High volume + strong order flow detected, **or**
  - High-impact news event is active

This is controlled in `core/scheduler.py`.

---

## Risk Rules (Default)

- Risk per trade: 0.75% of equity
- Max open positions: 4
- Daily loss limit: 2.8%
- Weekly loss limit: 7.5%
- Minimum Risk:Reward: 1:3

These can be changed in `core/config.py`.

---

## Disclaimer

This software is provided for educational and research purposes.  
Trading involves substantial risk of loss. Use at your own risk.
