from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class ExchangeAdapter(ABC):
    """
    Base interface that every exchange adapter must implement.
    Later you will create CoinbaseAdapter, DeltaAdapter, MT5Adapter etc.
    that inherit from this class.
    """

    name: str = "base"

    @abstractmethod
    async def get_equity(self) -> float:
        """Return current account equity in quote currency (usually USD/USDT)."""
        pass

    @abstractmethod
    async def get_price(self, symbol: str) -> float:
        """Return current mid/last price for the symbol."""
        pass

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "market"
    ) -> Dict[str, Any]:
        """
        Place an order.
        Must return a dict containing at least: {"order_id": "...", "status": "..."}
        """
        pass

    @abstractmethod
    async def close_position(
        self,
        symbol: str,
        side: str,
        size: float
    ) -> float:
        """
        Close an existing position.
        Returns realized PnL.
        """
        pass

    @abstractmethod
    async def get_open_positions(self) -> list:
        """Return list of currently open positions on this platform."""
        pass

    async def health_check(self) -> bool:
        """Optional: return True if the connection is healthy."""
        return True
