"""
MyFundedPerps Adapter (Prop Firm)
---------------------------------
Base URL: https://developers.myfundedperpetuals.com/v1
Auth: Bearer token (API Key)

Note: This is a prop-firm / challenge platform, not a regular exchange.
API is currently in beta.
"""

from typing import Optional, Dict, Any, List
import logging
import httpx
from .base import ExchangeAdapter

log = logging.getLogger("MyfundedperpsAdapter")


class MyfundedperpsAdapter(ExchangeAdapter):
    name = "myfundedperps"

    def __init__(self, api_key: str = "", base_url: str = "https://developers.myfundedperpetuals.com/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def get_equity(self) -> float:
        try:
            # Example – adjust to actual endpoint from their docs
            r = await self.client.get(f"{self.base_url}/accounts", headers=self.headers)
            r.raise_for_status()
            data = r.json()
            # Parse according to their response structure
            return float(data.get("data", [{}])[0].get("equity", 0) or 0)
        except Exception as e:
            log.error("Myfundedperps get_equity error: %s", e)
            return 0.0

    async def get_price(self, symbol: str) -> float:
        try:
            r = await self.client.get(f"{self.base_url}/markets/{symbol}", headers=self.headers)
            r.raise_for_status()
            data = r.json()
            return float(data.get("data", {}).get("price", 0) or 0)
        except Exception as e:
            log.error("Myfundedperps get_price error: %s", e)
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
        payload = {
            "symbol": symbol,
            "side": side.lower(),
            "size": size,
            "type": order_type,
        }
        if stop_loss:
            payload["stop_loss"] = stop_loss
        if take_profit:
            payload["take_profit"] = take_profit

        try:
            r = await self.client.post(f"{self.base_url}/orders", headers=self.headers, json=payload)
            r.raise_for_status()
            data = r.json()
            order_id = str(data.get("data", {}).get("id") or data.get("id"))
            log.info("Myfundedperps order: %s %s → %s", side, symbol, order_id)
            return {"order_id": order_id, "status": "submitted", "symbol": symbol, "side": side, "size": size}
        except Exception as e:
            log.error("Myfundedperps place_order failed: %s", e)
            raise

    async def close_position(self, symbol: str, side: str, size: float) -> float:
        opposite = "sell" if side.lower() == "buy" else "buy"
        try:
            await self.place_order(symbol, opposite, size)
            return 0.0
        except Exception as e:
            log.error("Myfundedperps close error: %s", e)
            return 0.0

    async def get_open_positions(self) -> List[Dict]:
        try:
            r = await self.client.get(f"{self.base_url}/positions", headers=self.headers)
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as e:
            log.error("Myfundedperps positions error: %s", e)
            return []

    async def health_check(self) -> bool:
        try:
            r = await self.client.get(f"{self.base_url}", headers=self.headers)
            return r.status_code == 200
        except Exception:
            return False
