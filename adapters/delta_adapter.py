"""
Delta Exchange India Adapter
----------------------------
Base URL: https://api.india.delta.exchange

Authentication: HMAC-SHA256
Headers required: api-key, signature, timestamp, User-Agent
"""

import time
import hmac
import hashlib
import json
from typing import Optional, Dict, Any, List
import logging
import httpx
from .base import ExchangeAdapter

log = logging.getLogger("DeltaAdapter")


class DeltaAdapter(ExchangeAdapter):
    name = "delta"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        base_url: str = "https://api.india.delta.exchange"
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _sign(self, method: str, path: str, query: str = "", body: str = "") -> Dict[str, str]:
        timestamp = str(int(time.time()))
        prehash = method.upper() + timestamp + path + query + body
        signature = hmac.new(
            self.api_secret.encode(),
            prehash.encode(),
            hashlib.sha256
        ).hexdigest()

        return {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
            "User-Agent": "GrokTradingBrain/1.0",
            "Content-Type": "application/json"
        }

    async def _request(self, method: str, path: str, params: dict = None, body: dict = None):
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())

        body_str = json.dumps(body) if body else ""
        headers = self._sign(method, path, query, body_str)

        url = self.base_url + path + query
        response = await self.client.request(method, url, headers=headers, content=body_str or None)
        response.raise_for_status()
        return response.json()

    async def get_equity(self) -> float:
        try:
            data = await self._request("GET", "/v2/wallet/balances")
            # Sum USDT balance
            for item in data.get("result", []):
                if item.get("asset_symbol") == "USDT":
                    return float(item.get("available_balance", 0))
            return 0.0
        except Exception as e:
            log.error("Delta get_equity error: %s", e)
            return 0.0

    async def get_price(self, symbol: str) -> float:
        try:
            # Delta uses symbols like BTCUSD, ETHUSD
            clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
            if clean.endswith("USDT"):
                clean = clean.replace("USDT", "USD")
            data = await self._request("GET", f"/v2/tickers/{clean}")
            return float(data.get("result", {}).get("close", 0) or data.get("result", {}).get("mark_price", 0))
        except Exception as e:
            log.error("Delta get_price error (%s): %s", symbol, e)
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
        clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
        if clean.endswith("USDT"):
            clean = clean.replace("USDT", "USD")

        body = {
            "product_id": None,          # You should resolve product_id from symbol
            "product_symbol": clean,
            "size": size,
            "side": side.lower(),
            "order_type": "market_order" if order_type == "market" else "limit_order",
        }

        # Note: For production you must map symbol → product_id correctly
        try:
            data = await self._request("POST", "/v2/orders", body=body)
            result = data.get("result", {})
            order_id = str(result.get("id"))
            log.info("Delta order placed: %s %s → %s", side, symbol, order_id)
            return {
                "order_id": order_id,
                "status": result.get("state", "submitted"),
                "symbol": symbol,
                "side": side.upper(),
                "size": size
            }
        except Exception as e:
            log.error("Delta place_order failed: %s", e)
            raise

    async def close_position(self, symbol: str, side: str, size: float) -> float:
        opposite = "sell" if side.lower() == "buy" else "buy"
        try:
            await self.place_order(symbol, opposite, size)
            return 0.0
        except Exception as e:
            log.error("Delta close error: %s", e)
            return 0.0

    async def get_open_positions(self) -> List[Dict]:
        try:
            data = await self._request("GET", "/v2/positions")
            return data.get("result", [])
        except Exception as e:
            log.error("Delta positions error: %s", e)
            return []

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/v2/wallet/balances")
            return True
        except Exception:
            return False
