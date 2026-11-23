"""
Binance Futures (USDT-M) Adapter
--------------------------------
Base URL: https://fapi.binance.com

Authentication: HMAC-SHA256
Headers required: X-MBX-APIKEY, timestamp, signature
"""

import time
import hmac
import hashlib
from typing import Optional, Dict, Any, List
import logging
import httpx
from .base import ExchangeAdapter

log = logging.getLogger("BinanceAdapter")


class BinanceAdapter(ExchangeAdapter):
    name = "binance"

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        base_url: str = "https://fapi.binance.com"
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=15.0)
        self._last_equity = 0.0

    def _sign(self, query: str = "") -> str:
        if not self.api_secret:
            return ""
        return hmac.new(
            self.api_secret.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def _normalize_symbol(self, symbol: str) -> str:
        clean = symbol.upper().replace("/", "").replace("-", "").replace("_", "")
        if clean.endswith("PERPETUAL"):
            clean = clean.replace("PERPETUAL", "")
        if clean.endswith("USD") and not clean.endswith("USDT") and not clean.endswith("BUSD"):
            clean = clean[:-3] + "USDT"
        if not clean.endswith("USDT"):
            clean = clean + "USDT"
        return clean

    async def get_equity(self) -> float:
        """Fetch total margin balance / wallet balance in USDT."""
        if not self.api_key or not self.api_secret:
            return self._last_equity or 0.0

        timestamp = int(time.time() * 1000)
        query = f"timestamp={timestamp}"
        signature = self._sign(query)
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            url = f"{self.base_url}/fapi/v2/account?{query}&signature={signature}"
            resp = await self.client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                total_margin = float(data.get("totalMarginBalance", 0.0) or data.get("totalWalletBalance", 0.0) or 0.0)
                if total_margin > 0:
                    self._last_equity = round(total_margin, 2)
                    return self._last_equity
            else:
                log.warning("Binance get_equity HTTP %s: %s", resp.status_code, resp.text)
        except Exception as e:
            log.error("Binance get_equity error: %s", e)

        return self._last_equity or 0.0

    async def get_price(self, symbol: str) -> float:
        """Fetch current mark or ticker price for symbol."""
        sym_norm = self._normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/fapi/v1/ticker/price?symbol={sym_norm}"
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return float(resp.json().get("price", 0.0) or 0.0)
        except Exception as e:
            log.debug("Binance get_price error for %s: %s", sym_norm, e)
        return 0.0

    async def get_candles(self, symbol: str, interval: str = "5m", limit: int = 48) -> List[Dict[str, Any]]:
        """Fetch public OHLCV candles from Binance Futures."""
        sym_norm = self._normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/fapi/v1/klines?symbol={sym_norm}&interval={interval}&limit={limit}"
            resp = await self.client.get(url)
            if resp.status_code == 200:
                raw = resp.json()
                candles = []
                for k in raw:
                    candles.append({
                        "start": int(k[0] // 1000),
                        "open": float(k[1]),
                        "high": float(k[2]),
                        "low": float(k[3]),
                        "close": float(k[4]),
                        "volume": float(k[5])
                    })
                return candles
        except Exception as e:
            log.error("Binance get_candles error for %s: %s", sym_norm, e)
        return []

    async def place_order(
        self,
        symbol: str,
        side: str,
        size: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        order_type: str = "market",
        leverage: str = "10"
    ) -> Dict[str, Any]:
        """Place market order on Binance USDT-M Futures."""
        sym_norm = self._normalize_symbol(symbol)
        side_norm = side.upper()
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Binance API key and secret are required for live orders.")

        timestamp = int(time.time() * 1000)
        params = [
            f"symbol={sym_norm}",
            f"side={side_norm}",
            f"type={order_type.upper()}",
            f"quantity={size}",
            f"timestamp={timestamp}"
        ]
        query = "&".join(params)
        signature = self._sign(query)
        headers = {"X-MBX-APIKEY": self.api_key}

        url = f"{self.base_url}/fapi/v1/order?{query}&signature={signature}"
        resp = await self.client.post(url, headers=headers)
        if resp.status_code == 200:
            res_data = resp.json()
            order_id = str(res_data.get("orderId", ""))
            log.info("Binance order executed: %s %s size=%s oid=%s", side_norm, sym_norm, size, order_id)
            return {
                "order_id": order_id,
                "status": res_data.get("status", "FILLED").lower(),
                "symbol": sym_norm,
                "side": side_norm,
                "size": size
            }
        else:
            err_msg = resp.text
            log.error("Binance order error (%s): %s", resp.status_code, err_msg)
            raise RuntimeError(f"Binance order failed: {err_msg}")

    async def close_position(self, symbol: str, side: str, size: float) -> float:
        """Close open position using opposite market order."""
        opposite = "SELL" if side.upper() == "BUY" else "BUY"
        try:
            await self.place_order(symbol, opposite, size)
            return 0.0
        except Exception as e:
            log.error("Binance close_position error: %s", e)
            return 0.0

    async def get_open_positions(self) -> List[Dict]:
        """Fetch open positions with size != 0."""
        if not self.api_key or not self.api_secret:
            return []

        timestamp = int(time.time() * 1000)
        query = f"timestamp={timestamp}"
        signature = self._sign(query)
        headers = {"X-MBX-APIKEY": self.api_key}

        try:
            url = f"{self.base_url}/fapi/v2/positionRisk?{query}&signature={signature}"
            resp = await self.client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                parsed = []
                for p in data:
                    amt = float(p.get("positionAmt", 0.0) or 0.0)
                    if amt != 0.0:
                        entry_p = float(p.get("entryPrice", 0.0) or 0.0)
                        mark_p = float(p.get("markPrice", 0.0) or 0.0)
                        pnl = float(p.get("unRealizedProfit", 0.0) or 0.0)
                        lev = float(p.get("leverage", 1.0) or 1.0)
                        parsed.append({
                            "symbol": p.get("symbol"),
                            "side": "BUY" if amt > 0 else "SELL",
                            "size": abs(amt),
                            "entry_price": entry_p,
                            "mark_price": mark_p,
                            "unrealized_pnl": round(pnl, 4),
                            "leverage": lev
                        })
                return parsed
        except Exception as e:
            log.error("Binance get_open_positions error: %s", e)
        return []

    async def health_check(self) -> bool:
        try:
            r = await self.client.get(f"{self.base_url}/fapi/v1/ping")
            return r.status_code == 200
        except Exception:
            return False
