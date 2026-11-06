"""
TEMPLATE – Copy this file and implement a real exchange.

Example:
    - coinbase_adapter.py
    - delta_adapter.py
    - mt5_adapter.py
"""

from typing import Optional, Dict, Any
from .base import ExchangeAdapter


class ExampleExchangeAdapter(ExchangeAdapter):
    name = "example"

    def __init__(self, api_key: str = "", api_secret: str = "", passphrase: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        # Initialize your SDK / REST client here

    async def get_equity(self) -> float:
        # TODO: Call exchange balance endpoint
        raise NotImplementedError("Implement get_equity")

    async def get_price(self, symbol: str) -> float:
        # TODO: Call ticker endpoint
        raise NotImplementedError("Implement get_price")

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "market"
    ) -> Dict[str, Any]:
        # TODO: Place real order + optional SL/TP
        raise NotImplementedError("Implement place_order")

    async def close_position(self, symbol: str, side: str, size: float) -> float:
        # TODO: Close position and return realized PnL
        raise NotImplementedError("Implement close_position")

    async def get_open_positions(self) -> list:
        # TODO: Fetch open positions
        raise NotImplementedError("Implement get_open_positions")
