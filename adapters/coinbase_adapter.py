"""
Coinbase Advanced Trade Adapter
--------------------------------
Uses official SDK: coinbase-advanced-py

Install:
    pip install coinbase-advanced-py

Create API keys at: https://portal.cdp.coinbase.com/
"""

from typing import Optional, Dict, Any, List
import logging
from .base import ExchangeAdapter

log = logging.getLogger("CoinbaseAdapter")


class CoinbaseAdapter(ExchangeAdapter):
    name = "coinbase"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None

        if api_key and api_secret:
            try:
                from coinbase.rest import RESTClient
                self.client = RESTClient(api_key=api_key, api_secret=api_secret)
                log.info("Coinbase client initialized")
            except ImportError:
                log.error("Please install: pip install coinbase-advanced-py")
            except Exception as e:
                log.error("Coinbase init failed: %s", e)

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT → BTC-USD (Coinbase style)"""
        s = symbol.upper().replace("/", "-").replace("_", "-")
        if s.endswith("-USDT"):
            s = s.replace("-USDT", "-USD")
        return s

    async def get_equity(self) -> float:
        if not self.client:
            return 0.0
        try:
            accounts = self.client.get_accounts()
            total = 0.0
            for acc in accounts.get("accounts", []):
                if acc.get("currency") in ["USD", "USDT", "USDC"]:
                    total += float(acc.get("available_balance", {}).get("value", 0))
            return round(total, 2)
        except Exception as e:
            log.error("Coinbase get_equity error: %s", e)
            return 0.0

    async def get_price(self, symbol: str) -> float:
        if not self.client:
            return 0.0
        try:
            product_id = self._normalize_symbol(symbol)
            product = self.client.get_product(product_id)
            return float(product.get("price", 0))
        except Exception as e:
            log.error("Coinbase get_price error (%s): %s", symbol, e)
            return 0.0

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "market"
    ) -> Dict[str, Any]:
        if not self.client:
            raise RuntimeError("Coinbase client not initialized")

        product_id = self._normalize_symbol(symbol)
        side = side.lower()

        try:
            if order_type == "market":
                if side == "buy":
                    order = self.client.market_order_buy(
                        client_order_id=None,
                        product_id=product_id,
                        quote_size=str(round(size * await self.get_price(symbol), 2))
                    )
                else:
                    order = self.client.market_order_sell(
                        client_order_id=None,
                        product_id=product_id,
                        base_size=str(size)
                    )
            else:
                raise NotImplementedError("Only market orders implemented in this version")

            order_id = order.get("order_id") or order.get("success_response", {}).get("order_id")
            log.info("Coinbase order placed: %s %s %s", side, symbol, order_id)

            return {
                "order_id": order_id,
                "status": "submitted",
                "symbol": symbol,
                "side": side.upper(),
                "size": size
            }
        except Exception as e:
            log.error("Coinbase place_order failed: %s", e)
            raise

    async def close_position(self, symbol: str, side: str, size: float) -> float:
        opposite = "SELL" if side.upper() == "BUY" else "BUY"
        try:
            await self.place_order(symbol, opposite, size)
            return 0.0
        except Exception as e:
            log.error("Coinbase close_position error: %s", e)
            return 0.0

    async def get_open_positions(self) -> List[Dict]:
        return []

    async def health_check(self) -> bool:
        try:
            if self.client:
                self.client.get_accounts()
                return True
        except Exception:
            pass
        return False
