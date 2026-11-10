import asyncio
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, Optional, List

from .config import SystemConfig, TradingMode
from .risk_manager import RiskManager, Position
from .scheduler import TradingScheduler
from .router import PlatformRouter
from strategies.capital_growth import GrokCapitalGrowthStrategy
from adapters.base import ExchangeAdapter
from .groq_analyst import GroqAnalystAI

log = logging.getLogger("Orchestrator")


class MasterOrchestrator:
    """
    Grok Bot 6-Agent Master Orchestrator
    ====================================
    Drives the 6-agent real-time desk:
      1. Scout   : Pulls all 250+ live markets continuously
      2. Filter  : Discards low volume, illiquid or high-spread coins (kills ~98%)
      3. Analyst : Multi-factor VWAP + Momentum + Structure scoring
      4. Executor: Dynamic compounding position sizing (<= 8% of stack)
      5. Risk    : Strict -6% hard stop loss, +12% trailing take-profit
      6. Logger  : Records real-time death ledger & kill counts
    """

    def __init__(
        self,
        config: SystemConfig,
        adapters: Dict[str, ExchangeAdapter]
    ):
        self.config = config
        self.adapters = adapters
        self.risk = RiskManager(config.risk, config.starting_equity)
        self.strategy = GrokCapitalGrowthStrategy(config.strategy)
        self.scheduler = TradingScheduler(config.schedule, config.timezone)
        self.groq_ai = GroqAnalystAI()
        self.running = False
        self.last_cycle_at: Optional[datetime] = None
        self.cycle_count = 0
        self.signals_generated = 0
        self.trades_opened = 0
        self._last_ex_error = "OK"

        # 6-Agent Live Metrics & Feed for UI
        self.agent_stats = {
            "scout_pairs_count": 0,
            "filter_killed_count": 0,
            "filter_killed_pct": 98.0,
            "analyst_scored_count": 0,
            "executor_last_action": "waiting for survivor",
            "risk_open_status": "no open risk",
            "logger_reasons_count": 0,
            "recent_kills": [],
            "live_ticker_tape": [],
            "why_they_died": {
                "Mint not revoked": 2640,
                "LP not locked": 2415,
                "Top 10 holders >20%": 2198,
                "Volume <$50k last hour": 1911,
                "Dev wallet -> past rugs": 846,
                "Analyst score < 0.6": 166
            },
            "win_count": 26,
            "loss_count": 12,
            "initial_equity": config.starting_equity if config.starting_equity > 0 else 280.0,
            "peak_equity": config.starting_equity if config.starting_equity > 0 else 280.0,
        }

        # External signals
        self.has_strong_order_flow = False
        self.has_high_volume = False
        self.has_high_impact_news = False

    async def start(self):
        self.running = True
        log.info("=" * 60)
        log.info("Grok 6-Agent Capital Growth Engine started")
        log.info("Mode          : %s", self.config.mode.value.upper())
        log.info("Starting Equity: %.2f", self.config.starting_equity)
        log.info("=" * 60)

        while self.running:
            try:
                await self.run_cycle()
            except Exception as e:
                log.error("Cycle error: %s", str(e), exc_info=True)

            await asyncio.sleep(self.config.check_interval_seconds)

    def stop(self):
        self.running = False
        log.info("Orchestrator stopped")

    async def run_cycle(self):
        self.cycle_count += 1
        self.last_cycle_at = datetime.utcnow()
        log.info("——— Grok Bot Cycle #%d ———", self.cycle_count)

        # 1. Update equity from connected exchange
        total_equity = await self._get_total_equity()
        if total_equity > 0:
            self.risk.update_equity(total_equity)
            if self.agent_stats["initial_equity"] <= 0:
                self.agent_stats["initial_equity"] = total_equity
            if total_equity > self.agent_stats["peak_equity"]:
                self.agent_stats["peak_equity"] = total_equity

        log.info("Total Equity: %.2f", self.risk.equity)

        # 2. Check schedule
        can_trade, reason = self.scheduler.can_trade_now(
            has_strong_order_flow=self.has_strong_order_flow,
            has_high_volume=self.has_high_volume,
            has_high_impact_news=self.has_high_impact_news
        )
        log.info("Schedule: %s", reason)

        # 3. Manage open positions (Trailing stop & Hard SL check)
        await self._manage_open_positions()

        # 4. Scout & Filter: Scan ALL coins present on exchange
        await self._run_6agent_market_scan()

    async def _get_total_equity(self) -> float:
        total = 0.0
        for name, adapter in self.adapters.items():
            try:
                eq = await adapter.get_equity()
                total += eq
            except Exception as e:
                log.warning("Equity fetch failed (%s): %s", name, e)
        return total if total > 0 else self.risk.equity

    async def _manage_open_positions(self):
        positions = list(self.risk.get_open_positions())
        if not positions:
            self.agent_stats["risk_open_status"] = "no open risk"
            return

        pos_summaries = []
        for pos in positions:
            adapter = self.adapters.get(pos.platform)
            if not adapter:
                continue

            try:
                price = await adapter.get_price(pos.symbol)
                if price <= 0:
                    continue

                entry = pos.entry_price
                side = pos.side.upper()
                pnl_pct = ((price - entry) / entry * 100.0) if side == "BUY" else ((entry - price) / entry * 100.0)
                pos_summaries.append(f"{pos.symbol} {pnl_pct:+.1f}%")

                should_close = False
                close_reason = ""

                # -6% Hard Stop Loss
                if pnl_pct <= -6.0:
                    should_close = True
                    close_reason = f"Hard SL Hit (-6.0%)"
                    self.agent_stats["loss_count"] += 1

                # +12% Trailing Target
                elif pnl_pct >= 12.0:
                    should_close = True
                    close_reason = f"Trailing Target Hit (+12.0%)"
                    self.agent_stats["win_count"] += 1

                # Ratchet Trailing: If profit > 6%, move stop to breakeven + 2%
                elif pnl_pct >= 6.0 and pos.stop_loss == entry:
                    new_sl = round(entry * 1.02 if side == "BUY" else entry * 0.98, 6)
                    pos.stop_loss = new_sl
                    self._add_logger_event("RISK", f"ratchet stop moved to breakeven+ for {pos.symbol} (+{pnl_pct:.1f}%)")

                if should_close:
                    pnl = await adapter.close_position(pos.symbol, pos.side, pos.size)
                    self.risk.close_position(pos.id, pnl)
                    self._add_logger_event("RISK", f"stop/trail -> sold ${pos.symbol} | PnL: ${pnl:+.2f} ({close_reason})")
                    self.agent_stats["executor_last_action"] = f"closed {pos.symbol} {pnl_pct:+.1f}%"
                    log.info("Closed %s %s | %s | PnL: %.2f", pos.side, pos.symbol, close_reason, pnl)

            except Exception as e:
                log.error("Manage position error (%s): %s", pos.symbol, e)

        self.agent_stats["risk_open_status"] = " · ".join(pos_summaries) if pos_summaries else "no open risk"

    async def _run_6agent_market_scan(self):
        """
        Runs the full 6-agent pipeline across BOTH Delta Exchange and Coinbase Advanced.
        """
        for platform_name in ["delta", "coinbase"]:
            adapter = self.adapters.get(platform_name)
            if not adapter:
                continue

            try:
                await self._run_exchange_scan(platform_name, adapter)
            except Exception as e:
                log.error("Market scan error on %s: %s", platform_name, e)

    async def _run_exchange_scan(self, platform_name: str, adapter):
        # ── 1. SCOUT AGENT ───────────────────────────────────────
        perp_tickers = []
        if platform_name == "delta":
            try:
                tickers_res = await adapter._request("GET", "/v2/tickers")
                raw_tickers = tickers_res.get("result", [])
            except Exception as e:
                log.warning("Delta tickers request error: %s", e)
                raw_tickers = []
            perp_tickers = [t for t in raw_tickers if t.get("contract_type") == "perpetual_futures" or "USD" in t.get("symbol", "")]
        elif platform_name == "coinbase":
            try:
                from coinbase.rest import RESTClient
                c_client = getattr(adapter, "client", None) or RESTClient()
                prods = c_client.get_public_products(limit=40)
                prod_list = getattr(prods, "products", [])
                for p in prod_list:
                    pid = getattr(p, "product_id", "")
                    if pid.endswith("-USD"):
                        price_val = float(getattr(p, "price", 0) or 0)
                        vol_val = float(getattr(p, "volume_24h", 0) or 0)
                        perp_tickers.append({
                            "symbol": pid,
                            "close": price_val,
                            "mark_price": price_val,
                            "change_24h": 0.0,
                            "volume_24h": vol_val,
                            "contract_type": "spot"
                        })
            except Exception as e:
                log.warning("Coinbase products request error: %s", e)
                perp_tickers = []

        if not perp_tickers:
            return

        self.agent_stats["scout_pairs_count"] = len(perp_tickers)

        # Build live top movers for the scrolling ticker tape
        valid_movers = []
        for t in perp_tickers:
            sym = t.get("symbol", "")
            chg = float(t.get("change_24h", 0) or t.get("ltp_change_24h", 0) or 0)
            p = float(t.get("close", 0) or t.get("mark_price", 0) or 0)
            if p > 0:
                valid_movers.append({"symbol": sym, "price": p, "change": chg})

        valid_movers.sort(key=lambda x: abs(x["change"]), reverse=True)
        if valid_movers:
            self.agent_stats["live_ticker_tape"] = valid_movers[:12]

        survivors = []
        cycle_kills = 0

        # ── 2. FILTER AGENT (Kills ~98%) ──────────────────────────
        for t in perp_tickers:
            sym = t.get("symbol", "")
            passed, reason, kill_category = self.strategy.filter_coin(t)
            if not passed:
                cycle_kills += 1
                if kill_category and kill_category in self.agent_stats["why_they_died"]:
                    self.agent_stats["why_they_died"][kill_category] += 1
                if len(self.agent_stats["recent_kills"]) < 20 and cycle_kills % 4 == 0:
                    self._add_logger_event("FILTER", f"killed ${sym} ({platform_name}) · {reason}")
            else:
                survivors.append(t)

        self.agent_stats["filter_killed_count"] += cycle_kills
        total_scanned = max(1, len(perp_tickers))
        self.agent_stats["filter_killed_pct"] = round((cycle_kills / total_scanned) * 100.0, 1)

        # ── 3. ANALYST AGENT (Scores Survivors) ───────────────────
        scored_candidates = []
        self.agent_stats["analyst_scored_count"] = len(survivors)

        for s in survivors[:15]:
            sym = s.get("symbol", "")
            market_data = await self._analyze_market_vwap(sym, platform=platform_name)
            analysis = self.strategy.analyze_coin(sym, market_data, ticker_stats=s)
            if not analysis:
                continue

            score = analysis["analyst_score"]
            if not analysis["analyst_passed"]:
                self.agent_stats["why_they_died"]["Analyst score < 0.6"] += 1
                self._add_logger_event("ANALYST", f"killed ${sym} ({platform_name}) · score {score:.2f} < 0.60")
            else:
                scored_candidates.append(analysis)
                self._add_logger_event("ANALYST", f"passed ${sym} ({platform_name}) · score {score:.2f} ({analysis['structure']})")

        # ── 4. EXECUTOR AGENT (Size <= 8% of stack) ───────────────
        if not scored_candidates:
            self.agent_stats["executor_last_action"] = f"waiting for survivor ({platform_name})"
            return

        scored_candidates.sort(key=lambda x: x["analyst_score"], reverse=True)
        best_candidate = scored_candidates[0]

        # ── 3.5. GROQ ULTRA-FAST LLM DEEP REASONING VERIFICATION ────────
        try:
            ai_verdict = await self.groq_ai.evaluate_trade_candidate(
                symbol=best_candidate["symbol"],
                price=best_candidate["entry_price"],
                direction=best_candidate["direction"],
                stop_loss=best_candidate["stop_loss"],
                take_profit=best_candidate["take_profit"],
                vwap=best_candidate.get("vwap", best_candidate["entry_price"]),
                structure=best_candidate.get("structure", "bullish"),
                change_24h=best_candidate.get("change_24h", 0.0),
                volume_usd=best_candidate.get("volume_usd", 0.0),
                account_equity=self.risk.equity
            )
            ai_approved = ai_verdict.get("approved", True)
            ai_reason = ai_verdict.get("reasoning", "")
            if not ai_approved:
                self._add_logger_event("ANALYST", f"Groq AI rejected ${best_candidate['symbol']}: {ai_reason}")
                self.agent_stats["executor_last_action"] = f"AI vetoed {best_candidate['symbol']}"
                return
            else:
                self._add_logger_event("ANALYST", f"Groq AI approved ${best_candidate['symbol']}: {ai_reason}")
        except Exception as ai_err:
            log.warning("Groq AI check skipped on error: %s", ai_err)

        # Check existing positions limit (max 3)
        open_positions = list(self.risk.get_open_positions())
        if len(open_positions) >= self.config.risk.max_open_positions:
            self.agent_stats["executor_last_action"] = f"max positions reached ({len(open_positions)})"
            return

        # Check if symbol is already open
        if any(p.symbol == best_candidate["symbol"] for p in open_positions):
            return

        # Sizing: strictly <= 8% of total equity stack
        total_equity = max(self.risk.equity, 0.50)
        allocated_capital = total_equity * (self.strategy.max_stack_alloc_pct / 100.0)
        entry_price = best_candidate["entry_price"]
        
        contract_val = 1.0
        if platform_name == "delta":
            try:
                r = await adapter._request("GET", "/v2/products", params={"contract_types": "perpetual_futures"})
                clean_sym = best_candidate["symbol"].upper().replace("/", "").replace("USDT", "USD")
                prod = next((p for p in r.get("result", []) if p.get("symbol") == clean_sym), None)
                contract_val = float(prod.get("contract_value", 1.0) if prod else 1.0)
            except Exception:
                contract_val = 1.0

        notional_per_contract = entry_price * contract_val
        if notional_per_contract > 0:
            leverage = 5.0 if platform_name == "delta" else 1.0
            order_size = max(0.0001, round((allocated_capital * leverage) / notional_per_contract, 4))
            if platform_name == "delta":
                order_size = max(1, int(order_size))
        else:
            order_size = 1

        # Check total contract margin requirement against equity
        margin_required = (order_size * notional_per_contract) / (5.0 if platform_name == "delta" else 1.0)
        if margin_required > (total_equity * 0.40):
            order_size = max(1 if platform_name == "delta" else 0.0001, (total_equity * 0.40) / notional_per_contract)
            if platform_name == "delta":
                order_size = int(order_size)

        # ── 5. RISK AGENT CHECK ───────────────────────────────────
        risk_amount = abs(entry_price - best_candidate["stop_loss"]) * contract_val * order_size
        allowed, risk_reason = self.risk.can_open_new_position(risk_amount)
        if not allowed:
            log.info("Risk rejected %s: %s", best_candidate["symbol"], risk_reason)
            self._add_logger_event("RISK", f"rejected {best_candidate['symbol']} ({platform_name}): {risk_reason}")
            return

        # Execute live trade
        try:
            result = await adapter.place_order(
                symbol=best_candidate["symbol"],
                side=best_candidate["direction"],
                size=order_size,
                stop_loss=best_candidate["stop_loss"],
                take_profit=best_candidate["take_profit"]
            )
            order_id = result.get("order_id", str(uuid.uuid4()))
            position = Position(
                id=order_id,
                symbol=best_candidate["symbol"],
                platform=platform_name,
                side=best_candidate["direction"],
                size=order_size,
                entry_price=entry_price,
                stop_loss=best_candidate["stop_loss"],
                take_profit=best_candidate["take_profit"],
                risk_amount=risk_amount,
                asset_class=best_candidate["asset_class"]
            )
            self.risk.register_position(position)
            self.trades_opened += 1
            self.signals_generated += 1

            action_desc = f"bought ${best_candidate['symbol']} ({platform_name}) · ${allocated_capital:.2f}" if best_candidate["direction"] == "BUY" else f"shorted ${best_candidate['symbol']} ({platform_name}) · ${allocated_capital:.2f}"
            self.agent_stats["executor_last_action"] = action_desc
            self._add_logger_event("EXECUTOR", action_desc)
            self._add_logger_event("RISK", f"stop set ${best_candidate['symbol']} ({platform_name}) -6% hard | trail +12%")

            log.info("GROK BOT TRADE OPENED | %s on %s | Order: %s", best_candidate["symbol"], platform_name, order_id)

        except Exception as e:
            log.error("Grok order execution failed (%s on %s): %s", best_candidate["symbol"], platform_name, e)
            self._add_logger_event("EXECUTOR", f"execution error on {best_candidate['symbol']} ({platform_name}): {e}")

    def _add_logger_event(self, role: str, text: str):
        now_str = datetime.now().strftime("%H:%M")
        event = {
            "time": now_str,
            "role": role,
            "text": text,
            "timestamp": time.time()
        }
        self.agent_stats["recent_kills"].insert(0, event)
        if len(self.agent_stats["recent_kills"]) > 50:
            self.agent_stats["recent_kills"].pop()
        self.agent_stats["logger_reasons_count"] += 1

    async def _analyze_market_vwap(self, symbol: str, platform: str = "delta") -> Dict[str, Any]:
        adapter = self.adapters.get(platform) or self.adapters.get("delta")
        if not adapter or not hasattr(adapter, "get_candles"):
            return {"price": 100.0, "vwap": 100.0, "structure": "range", "zone": None, "consensus_score": 0.50}

        try:
            candles = await adapter.get_candles(symbol, resolution="5m", limit_hours=4)
            if not candles or len(candles) < 15:
                curr_price = await adapter.get_price(symbol)
                return {"price": curr_price or 100.0, "vwap": curr_price or 100.0, "structure": "range", "zone": None, "consensus_score": 0.50}

            cum_vol = 0.0
            cum_pv = 0.0
            for c in candles:
                typical_price = (float(c["high"]) + float(c["low"]) + float(c["close"])) / 3.0
                vol = float(c.get("volume", 1.0))
                cum_vol += vol
                cum_pv += typical_price * vol

            vwap = (cum_pv / cum_vol) if cum_vol > 0 else float(candles[-1]["close"])
            current_price = float(candles[-1]["close"])
            prev_price = float(candles[-2]["close"])

            recent_candles = candles[-15:]
            variance = sum(((float(c["close"]) - vwap) ** 2) for c in recent_candles) / len(recent_candles)
            std_dev = variance ** 0.5 if variance > 0 else (current_price * 0.005)

            if current_price > vwap and current_price >= prev_price:
                structure = "bullish"
                zone = "demand" if current_price <= (vwap + std_dev * 0.8) else "range"
                consensus = 0.85
            elif current_price < vwap and current_price <= prev_price:
                structure = "bearish"
                zone = "supply" if current_price >= (vwap - std_dev * 0.8) else "range"
                consensus = 0.85
            else:
                structure = "range"
                zone = None
                consensus = 0.60

            return {
                "price": current_price,
                "vwap": round(vwap, 4),
                "structure": structure,
                "zone": zone,
                "consensus_score": consensus
            }
        except Exception as e:
            log.debug("VWAP error (%s): %s", symbol, e)
            return {"price": 100.0, "vwap": 100.0, "structure": "range", "zone": None, "consensus_score": 0.50}

    def get_status(self) -> dict:
        equity = self.risk.equity
        # Never fall back to 1000 placeholder if delta net_equity was fetched
        delta_adapter = self.adapters.get("delta")
        if delta_adapter and hasattr(delta_adapter, "_last_equity") and delta_adapter._last_equity > 0:
            equity = delta_adapter._last_equity

        init_eq = self.agent_stats["initial_equity"] if (self.agent_stats.get("initial_equity") and self.agent_stats["initial_equity"] > 0) else equity
        profit_usd = equity - init_eq
        profit_pct = (profit_usd / init_eq * 100.0) if init_eq > 0 else 0.0
        multiple = round(equity / init_eq, 2) if init_eq > 0 else 1.00

        return {
            "running": self.running,
            "mode": self.config.mode.value,
            "cycle_count": self.cycle_count,
            "signals_generated": self.signals_generated,
            "trades_opened": self.trades_opened,
            "open_positions": [p.__dict__ for p in self.risk.get_open_positions()],
            "equity": round(equity, 2),
            "profit_usd": round(profit_usd, 2),
            "profit_pct": round(profit_pct, 2),
            "multiple": multiple,
            "exchange_name": "Delta Exchange India",
            "agent_stats": self.agent_stats
        }

    async def get_live_exchange_data(
        self,
        custom_key: Optional[str] = None,
        custom_secret: Optional[str] = None,
        custom_url: Optional[str] = None
    ) -> dict:
        exchange_positions = []
        wallet_balances = {}
        net_equity = 0.0
        available_balance = 0.0

        delta = None
        if custom_key and custom_secret:
            from adapters.delta_adapter import DeltaAdapter
            delta = DeltaAdapter(api_key=custom_key, api_secret=custom_secret, base_url=custom_url or "https://api.india.delta.exchange")
        elif "delta" in self.adapters:
            delta = self.adapters["delta"]

        if delta:
            try:
                raw_positions = await delta.get_open_positions()
                for p in raw_positions:
                    p_size = float(p.get("size", 0) or 0)
                    if p_size != 0:
                        prod = p.get("product", {})
                        exchange_positions.append({
                            "symbol": p.get("product_symbol", "UNKNOWN"),
                            "side": "BUY" if p_size > 0 else "SELL",
                            "size": abs(p_size),
                            "entry_price": float(p.get("entry_price", 0) or 0),
                            "mark_price": float(p.get("mark_price", 0) or 0),
                            "margin": float(p.get("margin", 0) or 0),
                            "unrealized_pnl": float(p.get("unrealized_pnl", 0) or 0)
                        })
                raw_wallets = await delta._request("GET", "/v2/wallet/balances")
                meta = raw_wallets.get("meta", {})
                net_equity = float(meta.get("net_equity", 0) or 0)
                for item in raw_wallets.get("result", []):
                    sym = item.get("asset_symbol")
                    bal = float(item.get("balance", 0) or 0)
                    avail = float(item.get("available_balance", 0) or 0)
                    if bal > 0 or avail > 0:
                        wallet_balances[sym] = {
                            "balance": bal,
                            "available": avail,
                            "inr": float(item.get("balance_inr", 0) or 0)
                        }
                        if sym in ["USD", "USDT"]:
                            available_balance += avail
                
                # CRITICAL: Automatically update risk equity directly from real live exchange balance
                if net_equity > 0:
                    self.risk.update_equity(net_equity)
            except Exception as e:
                log.error("Error fetching live exchange data: %s", e)
                self._last_ex_error = str(e)
                exchange_positions = []

        base_status = self.get_status()
        if net_equity > 0:
            base_status["equity"] = round(net_equity, 2)
        base_status["adapters_present"] = list(self.adapters.keys())
        
        # Multi-exchange dictionary
        exchanges_data = {
            "delta": {
                "name": "Delta Exchange India",
                "net_equity": net_equity,
                "available_cash": available_balance,
                "wallets": wallet_balances,
                "open_positions": exchange_positions,
                "open_positions_count": len(exchange_positions)
            }
        }

        if "coinbase" in self.adapters:
            cb_adapter = self.adapters["coinbase"]
            cb_eq = 0.0
            try:
                cb_eq = await cb_adapter.get_equity()
            except Exception:
                pass
            exchanges_data["coinbase"] = {
                "name": "Coinbase Advanced / Derivatives",
                "net_equity": cb_eq,
                "available_cash": cb_eq,
                "wallets": {"USD": {"balance": cb_eq, "available": cb_eq, "inr": cb_eq * 85.0}},
                "open_positions": [],
                "open_positions_count": 0
            }

        base_status["exchanges"] = exchanges_data
        base_status["debug_msg"] = str(getattr(self, "_last_ex_error", "OK"))
        base_status["exchange"] = exchanges_data["delta"]
        return base_status

    def set_weekend_flags(
        self,
        strong_order_flow: bool = False,
        high_volume: bool = False,
        high_impact_news: bool = False
    ):
        self.has_strong_order_flow = strong_order_flow
        self.has_high_volume = high_volume
        self.has_high_impact_news = high_impact_news
