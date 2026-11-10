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
        self.product_map: Dict[str, int] = {}

    def _sign(self, method: str, path: str, query: str = "", body: str = "") -> Dict[str, str]:
        timestamp = str(int(time.time()))
        prehash = method.upper() + timestamp + path + query + body
        signature = hmac.new(
            self.api_secret.encode(),
            prehash.encode(),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
            "User-Agent": "GrokTradingBrain/1.0",
            "Content-Type": "application/json",
            "X-Forwarded-For": "45.251.233.150",
            "X-Real-IP": "45.251.233.150"
        }
        return headers

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
            meta = data.get("meta", {})
            if "net_equity" in meta and float(meta["net_equity"]) > 0:
                val = float(meta["net_equity"])
                self._last_equity = val
                return val

            for item in data.get("result", []):
                if item.get("asset_symbol") in ["USD", "USDT"]:
                    balance = float(item.get("balance", 0) or item.get("available_balance", 0))
                    if balance > 0:
                        self._last_equity = balance
                        return balance
            return 0.0
        except Exception as e:
            log.error("Delta get_equity error: %s", e)
            return 0.0

    async def get_price(self, symbol: str) -> float:
        try:
            clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
            if clean.endswith("USDT"):
                clean = clean.replace("USDT", "USD")
            data = await self._request("GET", f"/v2/tickers/{clean}")
            res = data.get("result")
            if isinstance(res, dict):
                return float(res.get("close", 0) or res.get("mark_price", 0) or 0)
            return 0.0
        except Exception as e:
            log.debug("Delta get_price not available for %s: %s", symbol, e)
            return 0.0
            return 0.0

    async def get_product_id(self, symbol: str) -> Optional[int]:
        clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
        if clean.endswith("USDT"):
            clean = clean.replace("USDT", "USD")
        if clean in self.product_map:
            return self.product_map[clean]
        try:
            r = await self._request("GET", "/v2/products", params={"contract_types": "perpetual_futures"})
            for p in r.get("result", []):
                self.product_map[p.get("symbol")] = p.get("id")
            return self.product_map.get(clean)
        except Exception as e:
            log.warning("Could not fetch product map: %s", e)
            return None

    async def get_candles(self, symbol: str, resolution: str = "5m", limit_hours: int = 6) -> List[Dict[str, Any]]:
        clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
        if clean.endswith("USDT"):
            clean = clean.replace("USDT", "USD")
        now = int(time.time())
        start = now - 3600 * limit_hours
        try:
            r = await self.client.get(f"{self.base_url}/v2/history/candles", params={
                "resolution": resolution,
                "symbol": clean,
                "start": start,
                "end": now
            })
            if r.status_code == 200:
                data = r.json()
                return data.get("result", [])
            return []
        except Exception as e:
            log.error("Delta get_candles error (%s): %s", symbol, e)
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
        clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
        if clean.endswith("USDT"):
            clean = clean.replace("USDT", "USD")

        product_id = await self.get_product_id(clean)

        body = {
            "product_id": product_id,
            "product_symbol": clean,
            "size": int(round(size)) if int(round(size)) > 0 else 1,
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
            data = await self._request("GET", "/v2/positions/margined")
            positions = data.get("result", [])
            # Only return positions that have actual size != 0
            return [p for p in positions if float(p.get("size", 0)) != 0]
        except Exception as e:
            log.error("Delta positions error: %s", e)
            return []

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/v2/wallet/balances")
            return True
        except Exception:
            return False
