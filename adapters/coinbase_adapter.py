"""
Coinbase Advanced Trade Adapter
Uses official SDK: coinbase-advanced-py
Supports both RESTClient object and dict formats, public candles, and robust error handling.
"""

from typing import Optional, Dict, Any, List
import logging
import time
from .base import ExchangeAdapter

log = logging.getLogger("CoinbaseAdapter")


class CoinbaseAdapter(ExchangeAdapter):
    name = "coinbase"

    def __init__(self, api_key: str = "", api_secret: str = ""):
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        self._last_equity = 0.0

        if api_key and api_secret:
            try:
                from coinbase.rest import RESTClient
                self.client = RESTClient(api_key=api_key, api_secret=api_secret)
                log.info("Coinbase client initialized with provided credentials")
            except ImportError:
                log.error("Please install: pip install coinbase-advanced-py")
            except Exception as e:
                log.error("Coinbase init failed: %s", e)

    def _normalize_symbol(self, symbol: str) -> str:
        """Convert BTC/USDT or BTCUSD to BTC-USD (Coinbase style)"""
        s = symbol.upper().replace("/", "-").replace("_", "-")
        if s.endswith("-USDT"):
            s = s.replace("-USDT", "-USD")
        elif "-" not in s:
            if s.endswith("USD"):
                s = s[:-3] + "-USD"
            elif s.endswith("USDT"):
                s = s[:-4] + "-USD"
        return s

    async def get_equity(self) -> float:
        if not self.client:
            return 0.0
        try:
            import asyncio
            accounts = await asyncio.to_thread(self.client.get_accounts)
            acc_list = getattr(accounts, "accounts", None)
            if acc_list is None and isinstance(accounts, dict):
                acc_list = accounts.get("accounts", [])
            elif acc_list is None:
                acc_list = []

            total = 0.0
            for acc in acc_list:
                curr = getattr(acc, "currency", None) or (acc.get("currency") if isinstance(acc, dict) else "")
                if curr in ["USD", "USDT", "USDC"]:
                    avail = getattr(acc, "available_balance", None) or (acc.get("available_balance") if isinstance(acc, dict) else {})
                    val = getattr(avail, "value", None) or (avail.get("value") if isinstance(avail, dict) else 0)
                    total += float(val or 0)
            self._last_equity = round(total, 2)
            return self._last_equity
        except Exception as e:
            log.warning("Coinbase get_equity error: %s", e)
            return self._last_equity

    async def get_price(self, symbol: str) -> float:
        product_id = self._normalize_symbol(symbol)
        try:
            import asyncio
            if self.client:
                prod = await asyncio.to_thread(self.client.get_product, product_id)
                price = getattr(prod, "price", None) or (prod.get("price") if isinstance(prod, dict) else None)
                if price:
                    return float(price)
            # Fallback to public client
            from coinbase.rest import RESTClient
            pub = RESTClient()
            prod = await asyncio.to_thread(pub.get_public_product, product_id)
            price = getattr(prod, "price", None) or (prod.get("price") if isinstance(prod, dict) else None)
            return float(price or 0.0)
        except Exception as e:
            log.warning("Coinbase get_price error (%s): %s", symbol, e)
            return 0.0

    async def get_candles(self, symbol: str, resolution: str = "5m", limit_hours: int = 4) -> List[Dict[str, Any]]:
        """Fetches historical candles from Coinbase for strategy scoring."""
        product_id = self._normalize_symbol(symbol)
        now = int(time.time())
        start = now - (3600 * limit_hours)
        gran_map = {
            "1m": "ONE_MINUTE",
            "5m": "FIVE_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "30m": "THIRTY_MINUTE",
            "1h": "ONE_HOUR",
            "2h": "TWO_HOUR",
            "6h": "SIX_HOUR",
            "1d": "ONE_DAY"
        }
        gran = gran_map.get(resolution, "FIVE_MINUTE")
        try:
            import asyncio
            from coinbase.rest import RESTClient
            c_client = self.client or RESTClient()
            res = await asyncio.to_thread(
                c_client.get_public_candles,
                product_id,
                start=str(start),
                end=str(now),
                granularity=gran
            )
            candles = getattr(res, "candles", None) or (res.get("candles") if isinstance(res, dict) else [])
            parsed = []
            for c in candles:
                c_dict = c.to_dict() if hasattr(c, "to_dict") else (c if isinstance(c, dict) else {})
                parsed.append({
                    "start": int(c_dict.get("start", 0)),
                    "open": float(c_dict.get("open", 0)),
                    "high": float(c_dict.get("high", 0)),
                    "low": float(c_dict.get("low", 0)),
                    "close": float(c_dict.get("close", 0)),
                    "volume": float(c_dict.get("volume", 0))
                })
            parsed.sort(key=lambda x: x["start"])
            return parsed
        except Exception as e:
            log.warning("Coinbase get_candles failed for %s: %s", product_id, e)
            return []

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
        import uuid
        client_order_id = str(uuid.uuid4())

        try:
            if order_type == "market":
                if side == "buy":
                    curr_price = await self.get_price(symbol)
                    quote_val = str(round(size * curr_price, 2))
                    order = self.client.market_order_buy(
                        client_order_id=client_order_id,
                        product_id=product_id,
                        quote_size=quote_val
                    )
                else:
                    order = self.client.market_order_sell(
                        client_order_id=client_order_id,
                        product_id=product_id,
                        base_size=str(size)
                    )
            else:
                raise NotImplementedError("Only market orders implemented in this version")

            order_id = getattr(order, "order_id", None) or (order.get("order_id") if isinstance(order, dict) else None)
            if not order_id and isinstance(order, dict):
                order_id = order.get("success_response", {}).get("order_id")
            
            log.info("Coinbase order placed: %s %s order_id=%s", side, symbol, order_id)

            return {
                "order_id": order_id or f"cb_{int(time.time())}",
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
