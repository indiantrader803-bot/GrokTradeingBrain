import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

from .config import SystemConfig, TradingMode
from .risk_manager import RiskManager, Position
from .scheduler import TradingScheduler
from .router import PlatformRouter
from strategies.capital_growth import GrokCapitalGrowthStrategy
from adapters.base import ExchangeAdapter

log = logging.getLogger("Orchestrator")


class MasterOrchestrator:
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
        self.running = False
        self.last_cycle_at: Optional[datetime] = None
        self.cycle_count = 0
        self.signals_generated = 0
        self.trades_opened = 0

        # External signals you can feed later
        self.has_strong_order_flow = False
        self.has_high_volume = False
        self.has_high_impact_news = False

    async def start(self):
        self.running = True
        log.info("=" * 60)
        log.info("Grok Capital Growth Engine started")
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
        log.info("——— Cycle #%d ———", self.cycle_count)

        # 1. Update equity
        total_equity = await self._get_total_equity()
        self.risk.update_equity(total_equity)
        log.info("Total Equity: %.2f", total_equity)

        # 2. Check schedule
        can_trade, reason = self.scheduler.can_trade_now(
            has_strong_order_flow=self.has_strong_order_flow,
            has_high_volume=self.has_high_volume,
            has_high_impact_news=self.has_high_impact_news
        )
        log.info("Schedule: %s", reason)

        if not can_trade:
            return

        # 3. Manage existing positions (simple TP/SL check)
        await self._manage_open_positions()

        # 4. Scan symbols
        symbols = (
            self.config.strategy.crypto_majors +
            self.config.strategy.metals +
            self.config.strategy.indices +
            self.config.strategy.forex_majors
        )

        for symbol in symbols:
            await self._evaluate_symbol(symbol)

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
        for pos in list(self.risk.get_open_positions()):
            adapter = self.adapters.get(pos.platform)
            if not adapter:
                continue

            try:
                price = await adapter.get_price(pos.symbol)
                should_close = False

                if pos.side == "BUY":
                    if price <= pos.stop_loss or price >= pos.take_profit:
                        should_close = True
                else:
                    if price >= pos.stop_loss or price <= pos.take_profit:
                        should_close = True

                if should_close:
                    pnl = await adapter.close_position(pos.symbol, pos.side, pos.size)
                    self.risk.close_position(pos.id, pnl)
                    log.info("Auto-closed %s %s | PnL: %.2f", pos.side, pos.symbol, pnl)

            except Exception as e:
                log.error("Manage position error (%s): %s", pos.symbol, e)

    async def _evaluate_symbol(self, symbol: str):
        # -------------------------------------------------------
        # THIS IS WHERE YOU CONNECT YOUR REAL SUPER BRAIN LATER
        # For now we use a placeholder market_data structure.
        # -------------------------------------------------------
        market_data = await self._get_market_data_placeholder(symbol)
        consensus = market_data.get("consensus_score", 0.0)

        signal = self.strategy.evaluate(symbol, market_data, consensus)
        if signal is None:
            return

        self.signals_generated += 1

        # Position sizing
        size = self.risk.calculate_position_size(
            signal["entry_price"],
            signal["stop_loss"]
        )
        if size <= 0:
            return

        risk_amount = abs(signal["entry_price"] - signal["stop_loss"]) * size

        allowed, reason = self.risk.can_open_new_position(risk_amount)
        if not allowed:
            log.info("Risk rejected %s: %s", symbol, reason)
            return

        # Choose platform
        platform = self._choose_platform(symbol)
        adapter = self.adapters.get(platform)
        if not adapter:
            log.warning("No adapter for platform: %s", platform)
            return

        # Execute
        try:
            if self.config.mode == TradingMode.DEMO:
                log.info(
                    "DEMO SIGNAL → %s %s | Size: %.6f | SL: %.4f | TP: %.4f | Conf: %.2f",
                    signal["direction"], symbol, size,
                    signal["stop_loss"], signal["take_profit"], signal["confidence"]
                )

            result = await adapter.place_order(
                symbol=symbol,
                side=signal["direction"],
                size=size,
                stop_loss=signal["stop_loss"],
                take_profit=signal["take_profit"]
            )

            position = Position(
                id=result.get("order_id", str(uuid.uuid4())),
                symbol=symbol,
                platform=platform,
                side=signal["direction"],
                size=size,
                entry_price=signal["entry_price"],
                stop_loss=signal["stop_loss"],
                take_profit=signal["take_profit"],
                risk_amount=risk_amount,
                asset_class=signal["asset_class"]
            )
            self.risk.register_position(position)
            self.trades_opened += 1

            log.info(
                "TRADE OPENED | %s | %s %s | Order: %s",
                platform, signal["direction"], symbol, position.id
            )

        except Exception as e:
            log.error("Execution failed (%s): %s", symbol, e)

    def _choose_platform(self, symbol: str) -> Optional[str]:
        """
        Smart multi-exchange router.
        Supports: coinbase, delta, coinswitch, myfundedperps, mt5, paper
        """
        return PlatformRouter.get_best_platform(symbol, self.adapters)

    async def _get_market_data_placeholder(self, symbol: str) -> Dict[str, Any]:
        """
        PLACEHOLDER – Replace this entire method with your real
        NVIDIA Super Brain + structure detection later.
        """
        # Safe default: no trade
        return {
            "price": 100.0,
            "structure": "range",
            "zone": None,
            "stop_loss": 95.0,
            "take_profit": 115.0,
            "risk_reward": 3.0,
            "consensus_score": 0.50
        }

    def get_status(self) -> dict:
        return {
            "running": self.running,
            "mode": self.config.mode.value,
            "cycle_count": self.cycle_count,
            "signals_generated": self.signals_generated,
            "trades_opened": self.trades_opened,
            "last_cycle_at": self.last_cycle_at.isoformat() if self.last_cycle_at else None,
            "risk": self.risk.get_status(),
            "scheduler": self.scheduler.get_status(),
            "weekend_flags": {
                "strong_order_flow": self.has_strong_order_flow,
                "high_volume": self.has_high_volume,
                "high_impact_news": self.has_high_impact_news,
            }
        }

    async def get_live_exchange_data(self) -> dict:
        exchange_positions = []
        wallet_balances = {}
        net_equity = 0.0
        available_balance = 0.0

        if "delta" in self.adapters:
            delta = self.adapters["delta"]
            try:
                raw_positions = await delta.get_open_positions()
                for p in raw_positions:
                    size = float(p.get("size", 0))
                    entry = float(p.get("entry_price", 0) or 0)
                    mark = float(p.get("mark_price", 0) or 0)
                    upnl = float(p.get("unrealized_pnl", 0) or 0)
                    margin = float(p.get("margin", 0) or 0)
                    prod = p.get("product", {})
                    und = prod.get("underlying_asset", {})
                    exchange_positions.append({
                        "symbol": p.get("product_symbol", "N/A"),
                        "coin_name": und.get("name", p.get("product_symbol", "")),
                        "base_asset": und.get("symbol", p.get("product_symbol", "")),
                        "side": "BUY" if size > 0 else "SELL",
                        "size": abs(size),
                        "entry_price": entry,
                        "mark_price": mark,
                        "unrealized_pnl": upnl,
                        "margin": margin,
                        "leverage": prod.get("default_leverage", "10x"),
                        "liq_price": float(p.get("liquidation_price", 0) or 0),
                        "bankruptcy_price": float(p.get("bankruptcy_price", 0) or 0),
                        "commission": float(p.get("commission", 0) or 0),
                        "realized_funding": float(p.get("realized_funding", 0) or 0),
                        "updated_at": p.get("updated_at", "")
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
            except Exception as e:
                log.error("Error fetching live exchange data: %s", e)

        base_status = self.get_status()
        base_status["exchange"] = {
            "name": "Delta Exchange India",
            "net_equity": net_equity,
            "available_cash": available_balance,
            "wallets": wallet_balances,
            "open_positions": exchange_positions,
            "open_positions_count": len(exchange_positions)
        }
        return base_status

    # Methods you can call from the dashboard or external systems
    def set_weekend_flags(
        self,
        strong_order_flow: bool = False,
        high_volume: bool = False,
        high_impact_news: bool = False
    ):
        self.has_strong_order_flow = strong_order_flow
        self.has_high_volume = high_volume
        self.has_high_impact_news = high_impact_news
        log.info(
            "Weekend flags updated → Flow:%s Volume:%s News:%s",
            strong_order_flow, high_volume, high_impact_news
        )
