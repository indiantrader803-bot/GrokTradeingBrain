from typing import Optional, Dict, List
import logging

log = logging.getLogger("PlatformRouter")


class PlatformRouter:
    """
    Decides which exchange should handle a given symbol.
    You can change the priority order later according to your preference.
    """

    # Priority order when multiple platforms can trade the same symbol
    CRYPTO_PRIORITY = ["coinbase", "delta", "myfundedperps", "coinswitch", "paper"]
    TRADITIONAL_PRIORITY = ["mt5", "paper"]

    @staticmethod
    def detect_asset_class(symbol: str) -> str:
        s = symbol.upper().replace("/", "").replace("-", "").replace("_", "")

        memes = ["PEPE", "SHIB", "DOGE", "FLOKI", "BONK", "WIF", "MEME", "NEIRO"]
        if any(m in s for m in memes):
            return "memecoin"

        majors = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "AVAX", "DOT", "LINK"]
        if any(m in s for m in majors):
            return "crypto"

        if any(x in s for x in ["XAU", "XAG", "GOLD", "SILVER"]):
            return "metal"

        if any(x in s for x in ["US30", "US100", "NAS100", "NASDAQ", "SPX", "SP500", "DJ30", "DJIA"]):
            return "index"

        # Simple forex detection (6 letters)
        clean = s.replace("USDT", "").replace("USD", "")
        if len(s) in [6, 7] and s.isalpha():
            return "forex"

        return "crypto"  # default fallback

    @classmethod
    def get_best_platform(
        cls,
        symbol: str,
        available_adapters: Dict[str, any]
    ) -> Optional[str]:
        """
        Returns the best available platform name for the given symbol.
        """
        asset_class = cls.detect_asset_class(symbol)

        if asset_class in ["metal", "index", "forex"]:
            priority = cls.TRADITIONAL_PRIORITY
        else:
            priority = cls.CRYPTO_PRIORITY

        for platform in priority:
            if platform in available_adapters:
                return platform

        # Last resort
        if available_adapters:
            return list(available_adapters.keys())[0]

        return None

    @classmethod
    def get_supported_platforms_for_symbol(cls, symbol: str) -> List[str]:
        asset_class = cls.detect_asset_class(symbol)

        if asset_class in ["metal", "index", "forex"]:
            return ["mt5"]
        if asset_class == "memecoin":
            return ["delta", "myfundedperps", "coinswitch"]
        # Normal crypto
        return ["coinbase", "delta", "myfundedperps", "coinswitch", "mt5"]
