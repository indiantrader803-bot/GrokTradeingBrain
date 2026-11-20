from typing import Dict, Any, List, Optional
from core.indicators import TechnicalIndicators

class StrategyBase:
    name: str = "BaseStrategy"
    def evaluate(self, symbol: str, ticker: Dict[str, Any], candles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

class StrategyATrendPullback(StrategyBase):
    """
    STRATEGY A — TREND PULLBACK
    Conditions:
      - Trend established: EMA 21 > EMA 43 (bullish) or EMA 21 < EMA 43 (bearish)
      - Pullback: Price is near dynamic support (EMA 21/43) and VWAP
      - Momentum recovery: RSI between 40-60 recovering in trend direction
      - Valid stop placement: Outside recent swing / 1.5x ATR
    """
    name = "Strategy_A_Trend_Pullback"

    def evaluate(self, symbol: str, ticker: Dict[str, Any], candles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if len(candles) < 45:
            return None
        closes = [c["close"] for c in candles]
        current_price = closes[-1]
        ema21 = TechnicalIndicators.calculate_ema(closes, 21)
        ema43 = TechnicalIndicators.calculate_ema(closes, 43)
        vwap = TechnicalIndicators.calculate_vwap(candles[-30:])
        rsi = TechnicalIndicators.calculate_rsi(closes, 14)
        atr = TechnicalIndicators.calculate_atr(candles, 14) or (current_price * 0.015)

        # Bullish Pullback
        if ema21 > ema43 and current_price >= vwap and 42 <= rsi <= 62:
            sl = round(current_price - 1.5 * atr, 6)
            tp = round(current_price + 3.0 * atr, 6)
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "BUY",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.0,
                "reason": f"Trend Pullback: EMA21 ({ema21:.4f}) > EMA43 ({ema43:.4f}) | RSI {rsi:.1f} near VWAP"
            }

        # Bearish Pullback
        if ema21 < ema43 and current_price <= vwap and 38 <= rsi <= 58:
            sl = round(current_price + 1.5 * atr, 6)
            tp = round(current_price - 3.0 * atr, 6)
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "SELL",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.0,
                "reason": f"Trend Pullback: EMA21 ({ema21:.4f}) < EMA43 ({ema43:.4f}) | RSI {rsi:.1f} under VWAP"
            }
        return None

class StrategyBBreakout(StrategyBase):
    """
    STRATEGY B — BREAKOUT
    Conditions:
      - Defined resistance/support breakout
      - Volume expansion: Recent volume > 1.8x rolling volume
      - Reward/risk >= 2.5:1
    """
    name = "Strategy_B_Breakout"

    def evaluate(self, symbol: str, ticker: Dict[str, Any], candles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if len(candles) < 30:
            return None
        recent_window = candles[-20:]
        highest_high = max(c["high"] for c in recent_window[:-1])
        lowest_low = min(c["low"] for c in recent_window[:-1])
        current_candle = recent_window[-1]
        current_price = current_candle["close"]

        # Volume expansion check
        avg_vol = sum(c.get("volume", 1) for c in recent_window[:-1]) / (len(recent_window) - 1)
        cur_vol = current_candle.get("volume", 1)
        vol_surge = cur_vol >= 1.6 * avg_vol if avg_vol > 0 else True

        atr = TechnicalIndicators.calculate_atr(candles, 14) or (current_price * 0.02)

        # Bullish Breakout
        if current_price > highest_high and vol_surge:
            sl = round(highest_high - 1.2 * atr, 6)
            tp = round(current_price + 3.0 * atr, 6)
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "BUY",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.5,
                "reason": f"Resistance Breakout above {highest_high:.4f} with {cur_vol/max(avg_vol,1):.1f}x volume expansion"
            }

        # Bearish Breakdown
        if current_price < lowest_low and vol_surge:
            sl = round(lowest_low + 1.2 * atr, 6)
            tp = round(current_price - 3.0 * atr, 6)
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "SELL",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.5,
                "reason": f"Support Breakdown below {lowest_low:.4f} with {cur_vol/max(avg_vol,1):.1f}x volume expansion"
            }
        return None

class StrategyCMomentum(StrategyBase):
    """
    STRATEGY C — MOMENTUM
    Conditions:
      - Directional price acceleration
      - Strong volume turnover
      - No overextension (RSI between 55-75 for long, 25-45 for short)
    """
    name = "Strategy_C_Momentum"

    def evaluate(self, symbol: str, ticker: Dict[str, Any], candles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        chg_24h = float(ticker.get("change_24h", 0) or ticker.get("price_change_percent_24h", 0) or 0.0)
        closes = [c["close"] for c in candles] if candles else []
        current_price = closes[-1] if closes else float(ticker.get("mark_price", 0) or 0.0)
        rsi = TechnicalIndicators.calculate_rsi(closes, 14) if len(closes) >= 15 else 50.0

        if current_price <= 0:
            return None

        # Long Momentum
        if 4.0 <= chg_24h <= 30.0 and 55 <= rsi <= 74:
            sl = round(current_price * 0.96, 6)  # -4%
            tp = round(current_price * 1.10, 6)  # +10%
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "BUY",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.5,
                "reason": f"Upward Momentum: 24h {chg_24h:+.1f}% | RSI {rsi:.1f} (Not Overextended)"
            }

        # Short Momentum
        if -30.0 <= chg_24h <= -4.0 and 26 <= rsi <= 45:
            sl = round(current_price * 1.04, 6)  # +4%
            tp = round(current_price * 0.90, 6)  # -10%
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "SELL",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.5,
                "reason": f"Downward Momentum: 24h {chg_24h:+.1f}% | RSI {rsi:.1f} (Not Oversold)"
            }
        return None

class StrategyDReversal(StrategyBase):
    """
    STRATEGY D — REVERSAL
    Conditions:
      - Exhaustion: RSI extreme (>78 or <22)
      - Rejection wick / divergence
      - Reversal probability
    """
    name = "Strategy_D_Reversal"

    def evaluate(self, symbol: str, ticker: Dict[str, Any], candles: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        closes = [c["close"] for c in candles] if candles else []
        if len(closes) < 20:
            return None
        current_price = closes[-1]
        rsi = TechnicalIndicators.calculate_rsi(closes, 14)
        c = candles[-1]
        body = abs(c["close"] - c["open"])
        upper_wick = c["high"] - max(c["close"], c["open"])
        lower_wick = min(c["close"], c["open"]) - c["low"]

        # Bearish Reversal from Overbought
        if rsi >= 78 and upper_wick > 1.8 * max(body, 0.0001):
            sl = round(c["high"] * 1.01, 6)
            tp = round(current_price * 0.94, 6)
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "SELL",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.2,
                "reason": f"Bearish Exhaustion: RSI {rsi:.1f} with upper rejection wick"
            }

        # Bullish Reversal from Oversold
        if rsi <= 22 and lower_wick > 1.8 * max(body, 0.0001):
            sl = round(c["low"] * 0.99, 6)
            tp = round(current_price * 1.06, 6)
            return {
                "strategy": self.name,
                "symbol": symbol,
                "direction": "BUY",
                "entry_price": current_price,
                "stop_loss": sl,
                "take_profit": tp,
                "risk_reward": 2.2,
                "reason": f"Bullish Exhaustion: RSI {rsi:.1f} with lower rejection wick"
            }
        return None
