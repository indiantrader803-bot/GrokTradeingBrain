from typing import List, Dict, Any, Optional
import math

class TechnicalIndicators:
    """Calculates EMA, VWAP, RSI, MACD, and ATR from candle bars."""

    @staticmethod
    def calculate_ema(prices: List[float], period: int) -> float:
        if not prices or len(prices) < period:
            return prices[-1] if prices else 0.0
        multiplier = 2.0 / (period + 1)
        ema = sum(prices[:period]) / period
        for p in prices[period:]:
            ema = (p - ema) * multiplier + ema
        return ema

    @staticmethod
    def calculate_vwap(candles: List[Dict[str, Any]]) -> float:
        cum_vol_price = 0.0
        cum_vol = 0.0
        for c in candles:
            typical_price = (c["high"] + c["low"] + c["close"]) / 3.0
            v = c.get("volume", 1.0)
            cum_vol_price += typical_price * v
            cum_vol += v
        return cum_vol_price / cum_vol if cum_vol > 0 else (candles[-1]["close"] if candles else 0.0)

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(prices)):
            diff = prices[i] - prices[i - 1]
            if diff >= 0:
                gains.append(diff)
                losses.append(0.0)
            else:
                gains.append(0.0)
                losses.append(abs(diff))

        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period

        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calculate_atr(candles: List[Dict[str, Any]], period: int = 14) -> float:
        if len(candles) < 2:
            return 0.0
        trs = []
        for i in range(1, len(candles)):
            c = candles[i]
            prev_c = candles[i - 1]
            tr = max(
                c["high"] - c["low"],
                abs(c["high"] - prev_c["close"]),
                abs(c["low"] - prev_c["close"])
            )
            trs.append(tr)
        return sum(trs[-period:]) / min(len(trs), period) if trs else 0.0
