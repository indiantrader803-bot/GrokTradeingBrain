# ROADMAP: Delta AI Trading Platform Execution Plan

**Project Version:** 2.0.0-PROD  
**Target Completion:** Full end-to-end operational platform with 12-page dashboard, 7-agent committee, 4 strategies, paper/live mode, SQLite database, and Docker packaging.

---

## Phase 1: Core Architecture, Database & Delta Connectivity (Current)
- [x] Inspect existing credentials, server environment, and running processes.
- [x] Author `PROJECT_AUDIT.md`.
- [x] Author `ROADMAP.md` and initial `DEVELOPMENT_STATUS.md`.
- [ ] Implement robust SQLite Database Schema (`database.py`):
  - Configuration, Watchlist, Signals, Committee Decisions, Orders, Positions, Trade Journal, System Audit Logs.
- [ ] Implement formal Delta Exchange Adapter (`delta_client.py`):
  - Environment selection (`DELTA_ENV=production` or `testnet`).
  - Strict HMAC-SHA256 signature generator.
  - Endpoints: `GET /api/exchange/status`, tickers, products, candles (OHLC), order book, wallet balance, positions, orders, fills.
  - Safe error recovery, rate limit backoff, and idempotency protection.

---

## Phase 2: Market Data System & 0–100 Multi-Factor Scanner
- [ ] Dynamic Liquid Market Discovery (Perpetual Futures + Spot).
- [ ] Market Data Poller & WebSocket Fallback.
- [ ] 0–100 Point Ranked Scanner (`scanner.py`):
  - Trend (20 pts), Momentum (20 pts), Volume (15 pts), Market Structure (15 pts), Liquidity (10 pts), R:R (10 pts), Multi-timeframe Alignment (10 pts).
  - Generates ranked candidate watchlist with detailed metric breakdown.

---

## Phase 3: Seven-Agent Trading Committee & Strategy Modules
- [ ] Build Seven Independent Agent Classes (`agents/`):
  1. **Agent 1 — Scanner Agent**: Detects unusual volume & volatility.
  2. **Agent 2 — Trend Analyst Agent**: Evaluates EMA 9/21/43/200, VWAP, RSI, MACD, ATR across M1, M5, M15, H1.
  3. **Agent 3 — Momentum Hunter Agent**: Evaluates price velocity, volume acceleration, breakout continuation probability.
  4. **Agent 4 — Skeptic Agent**: Rejection specialist checking fakeouts, excessive spread, overextension, funding risk, slippage.
  5. **Agent 5 — Position Sizer Agent**: Calculates capital risk, margin, leverage, micro-balance safety ($3 capital check), stop-loss distance.
  6. **Agent 6 — Trader Agent**: The isolated execution gate. Requires un-vetoed committee approval, fresh market data, and deterministic validation.
  7. **Agent 7 — Journal Agent**: Persists every signal, rejection reason, agent vote, and trade fill to SQLite.
- [ ] Implement Four Algorithmic Trading Strategies (`strategies/`):
  - **Strategy A — Trend Pullback**: EMA alignment + pullback to dynamic support + VWAP confirmation.
  - **Strategy B — Breakout**: Support/resistance break + volume expansion + confirmation.
  - **Strategy C — Momentum**: Directional acceleration + volume surge + no overextension.
  - **Strategy D — Reversal**: Price exhaustion + rejection candle + momentum divergence.

---

## Phase 4: Risk Engine, Paper Trading & Position Reconciliation
- [ ] Independent Deterministic Risk Engine (`risk_engine.py`):
  - Micro-account capital checks ($3 starting balance, 1% risk per trade, 3% max daily loss).
  - Minimum contract sizing enforcement (`INSUFFICIENT CAPITAL FOR SAFE TRADE`).
  - Mandatory hard stop-loss and take-profit calculation.
  - Cooldown on consecutive losses, daily circuit breaker.
- [ ] Paper Trading Engine (`paper_engine.py`):
  - Default execution mode with simulated fills, slippage, and fee deductions.
  - Distinct mode flag, equity tracking, and trade records.
- [ ] Live Trading Gateway (`live_gateway.py`):
  - Requires explicit `LIVE_TRADING_ENABLED=true` switch.
  - Pre-order exchange position reconciliation (detects external exchange positions before placing orders).

---

## Phase 5: Telegram Integration & 12-Page Dark-Mode Web Dashboard
- [ ] Telegram Notification Service (`telegram_bot.py`):
  - Async non-blocking alerts for startup, shutdown, trade signals, risk rejections, fills, and daily P&L.
- [ ] Professional 12-Page Dark-Mode Dashboard (`frontend/` & `templates/`):
  - Page 1: Overview (Live equity, today's P&L, win rate, open positions, status).
  - Page 2: Live Markets (Price, 24h change, volume, funding, scanner score).
  - Page 3: AI Signals (Long/Short, entry, SL, TP, R:R, reason).
  - Page 4: Agent Committee (Individual card per agent with analysis, score, rejection reason).
  - Page 5: Positions (Live open contracts, mark price, PnL, margin, leverage).
  - Page 6: Orders (Open, pending, filled, cancelled).
  - Page 7: Journal (Full trade & rejection history).
  - Page 8: Analytics (Equity curve, daily P&L, strategy comparison).
  - Page 9: Risk Settings (Configurable limits, leverage slider, capital buffer).
  - Page 10: Exchange Status (Connection health, latency, permissions, environment).
  - Page 11: System Logs (Real-time audit log stream).
  - Page 12: Settings (Mode switcher, strategy selector, Telegram, scheduler).

---

## Phase 6: Automated Testing, Deployment & Package Generation
- [ ] Author and execute comprehensive test suite (`tests/`):
  - Delta connectivity, signature verification, market scanner, 7-agent consensus, risk limits, paper simulation, position reconciliation.
- [ ] Docker & Docker Compose setup with persistent SQLite storage and health checks.
- [ ] Author `TEST_REPORT.md`, `DEPLOYMENT.md`, `SECURITY.md`, and updated `README.md`.
- [ ] Generate final deployable `delta_ai_trading_platform_v2.zip`.
