from typing import Dict, Any, Optional
import logging

from core.config import StrategyConfig

log = logging.getLogger("CapitalGrowthStrategy")


class GrokCapitalGrowthStrategy:
    """
    Selective High Risk:Reward Structure Strategy
    Designed for small capital growth with capital preservation priority.
    """

    def __init__(self, config: StrategyConfig):
        self.config = config

    def detect_asset_class(self, symbol: str) -> str:
        s = symbol.upper().replace("/", "").replace("-", "")

        memes = ["PEPE", "SHIB", "DOGE", "FLOKI", "BONK", "WIF", "MEME"]
        if any(m in s for m in memes):
            return "memecoin"

        majors = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA"]
        if any(m in s for m in majors):
            return "crypto"

        if "XAU" in s or "XAG" in s or "GOLD" in s:
            return "metal"

        if any(x in s for x in ["US30", "US100", "NAS100", "SPX", "DJ30"]):
            return "index"

        if len(s) == 6 and s.isalpha():
            return "forex"

        return "other"

    def evaluate(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        consensus_score: float
    ) -> Optional[Dict[str, Any]]:
        """
        Returns a clean signal dict or None.
        """

        asset_class = self.detect_asset_class(symbol)

        # Higher bar for high-risk assets
        min_score = self.config.min_consensus_score
        if asset_class in ["memecoin", "other"]:
            min_score = self.config.min_consensus_high_risk

        if consensus_score < min_score:
            log.debug("%s rejected – low consensus (%.2f < %.2f)", symbol, consensus_score, min_score)
            return None

        structure = market_data.get("structure")          # bullish / bearish / range
        zone = market_data.get("zone")                    # demand / supply
        rr = float(market_data.get("risk_reward", 0))
        price = market_data.get("price")
        stop_loss = market_data.get("stop_loss")
        take_profit = market_data.get("take_profit")

        if structure not in ["bullish", "bearish"]:
            return None
        if zone not in ["demand", "supply"]:
            return None
        if not all([price, stop_loss, take_profit]):
            return None

        # Minimum R:R rules
        min_rr = 3.0
        if asset_class in ["forex", "index", "metal"]:
            min_rr = 2.5
        if asset_class == "memecoin":
            min_rr = 4.0

        if rr < min_rr:
            log.debug("%s rejected – RR too low (%.2f < %.2f)", symbol, rr, min_rr)
            return None

        # Direction
        if structure == "bullish" and zone == "demand":
            direction = "BUY"
        elif structure == "bearish" and zone == "supply":
            direction = "SELL"
        else:
            return None

        signal = {
            "symbol": symbol,
            "direction": direction,
            "entry_price": float(price),
            "stop_loss": float(stop_loss),
            "take_profit": float(take_profit),
            "risk_reward": round(rr, 2),
            "confidence": round(consensus_score, 3),
            "asset_class": asset_class,
            "strategy": "Grok_Capital_Growth_Engine",
            "reason": f"Structure={structure} | Zone={zone} | RR={rr:.2f} | Consensus={consensus_score:.2f}"
        }

        log.info("Signal generated → %s %s | %s", direction, symbol, signal["reason"])
        return signal
