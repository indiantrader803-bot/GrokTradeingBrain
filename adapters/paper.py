import uuid
import time
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

from .base import ExchangeAdapter

log = logging.getLogger("PaperAdapter")


class PaperAdapter(ExchangeAdapter):
    """
    Simulated exchange for Demo / Paper trading.
    Keeps everything in memory. Perfect for testing the full system safely.
    """

    name = "paper"

    def __init__(self, starting_equity: float = 1000.0):
        self.equity = starting_equity
        self.positions: Dict[str, Dict] = {}
        self.orders: List[Dict] = []
        # Simple price simulation store
        self.prices: Dict[str, float] = {
            "BTC/USDT": 67000.0,
            "ETH/USDT": 3200.0,
            "SOL/USDT": 180.0,
            "XAUUSD": 2650.0,
            "US30": 42500.0,
            "US100": 20500.0,
            "EURUSD": 1.0850,
        }

    async def get_equity(self) -> float:
        return round(self.equity, 2)

    async def get_price(self, symbol: str) -> float:
        # In real use you would fetch live price.
        # Here we just return a stored value (you can update it externally).
        return self.prices.get(symbol, 100.0)

    def update_price(self, symbol: str, price: float):
        self.prices[symbol] = price

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "market"
    ) -> Dict[str, Any]:

        price = await self.get_price(symbol)
        order_id = f"paper_{uuid.uuid4().hex[:10]}"

        position = {
            "id": order_id,
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry_price": price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "opened_at": datetime.utcnow().isoformat(),
        }

        self.positions[order_id] = position
        self.orders.append(position)

        log.info(
            "PAPER ORDER → %s %s | Size: %.6f | Entry: %.4f | SL: %s | TP: %s",
            side, symbol, size, price, stop_loss, take_profit
        )

        return {
            "order_id": order_id,
            "status": "filled",
            "filled_price": price,
            "symbol": symbol,
            "side": side,
            "size": size
        }

    async def close_position(self, symbol: str, side: str, size: float) -> float:
        # Find matching position
        to_close = None
        for pid, pos in self.positions.items():
            if pos["symbol"] == symbol and pos["side"] == side:
                to_close = pid
                break

        if not to_close:
            return 0.0

        pos = self.positions.pop(to_close)
        current_price = await self.get_price(symbol)

        if side == "BUY":
            pnl = (current_price - pos["entry_price"]) * size
        else:
            pnl = (pos["entry_price"] - current_price) * size

        self.equity += pnl

        log.info(
            "PAPER CLOSE → %s %s | PnL: %.2f | New Equity: %.2f",
            side, symbol, pnl, self.equity
        )
        return round(pnl, 2)

    async def get_open_positions(self) -> list:
        return list(self.positions.values())

    async def health_check(self) -> bool:
        return True
