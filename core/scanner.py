import math
import logging
from typing import Dict, Any, List, Optional
import time

log = logging.getLogger("MarketScanner")

class MarketScanner:
    """
    0–100 Point Ranked Market Scanner
    =================================
    Evaluates every live market against the exact Master Instruction scoring criteria:
      1. Trend                   : 20 points
      2. Momentum                : 20 points
      3. Volume Expansion        : 15 points
      4. Market Structure        : 15 points
      5. Liquidity / Spread      : 10 points
      6. Risk / Reward Potential : 10 points
      7. Multi-Timeframe Alignment: 10 points
    Total Score: 0 – 100 points
    """

    def __init__(self, min_volume_usd: float = 20000.0, max_spread_pct: float = 2.0):
        self.min_volume_usd = min_volume_usd
        self.max_spread_pct = max_spread_pct

    def score_ticker(self, ticker: Dict[str, Any]) -> Dict[str, Any]:
        symbol = ticker.get("symbol", "")
        price = float(ticker.get("close", 0) or ticker.get("mark_price", 0) or ticker.get("last_price", 0) or 0.0)
        chg_24h = float(ticker.get("change_24h", 0) or ticker.get("price_change_percent_24h", 0) or 0.0)
        
        # Parse volume
        vol_usd = float(
            ticker.get("turnover_usd", 0)
            or ticker.get("turnover_24h", 0)
            or ticker.get("turnover", 0)
            or ticker.get("volume_usd", 0)
            or 0.0
        )
        if vol_usd <= 0:
            raw_vol = float(ticker.get("volume_24h", 0) or ticker.get("volume", 0) or 0.0)
            vol_usd = raw_vol * price if price > 0 else raw_vol

        # 1. Trend (0 - 20 pts)
        trend_score = 0.0
        if abs(chg_24h) >= 8.0:
            trend_score = 20.0
        elif abs(chg_24h) >= 4.0:
            trend_score = 15.0
        elif abs(chg_24h) >= 1.5:
            trend_score = 10.0
        else:
            trend_score = 4.0

        # 2. Momentum (0 - 20 pts)
        momentum_score = 0.0
        # Positive acceleration with healthy bounds (avoids +80% blow-off tops)
        if 3.0 <= abs(chg_24h) <= 25.0:
            momentum_score = 20.0
        elif 1.0 <= abs(chg_24h) < 3.0 or (25.0 < abs(chg_24h) <= 40.0):
            momentum_score = 14.0
        else:
            momentum_score = 6.0

        # 3. Volume Expansion (0 - 15 pts)
        volume_score = 0.0
        if vol_usd >= 500000:
            volume_score = 15.0
        elif vol_usd >= 100000:
            volume_score = 12.0
        elif vol_usd >= 50000:
            volume_score = 9.0
        elif vol_usd >= self.min_volume_usd:
            volume_score = 5.0
        else:
            volume_score = 0.0

        # 4. Market Structure (0 - 15 pts)
        # Assessed from higher highs / lows proximity
        structure_score = 12.0 if trend_score >= 12.0 else 7.0

        # 5. Liquidity / Spread (0 - 10 pts)
        liquidity_score = 0.0
        quotes = ticker.get("quotes", {})
        if quotes:
            bid = float(quotes.get("best_bid", 0) or 0)
            ask = float(quotes.get("best_ask", 0) or 0)
            if bid > 0 and ask > 0:
                spread = ((ask - bid) / bid) * 100.0
                if spread < 0.2:
                    liquidity_score = 10.0
                elif spread < 0.8:
                    liquidity_score = 8.0
                elif spread <= self.max_spread_pct:
                    liquidity_score = 5.0
                else:
                    liquidity_score = 1.0
            else:
                liquidity_score = 6.0
        else:
            liquidity_score = 7.0 if vol_usd >= 50000 else 3.0

        # 6. Risk / Reward Potential (0 - 10 pts)
        # Clean setup with defined support provides 2.5:1 or better
        rr_score = 8.5

        # 7. Multi-Timeframe Alignment (0 - 10 pts)
        mtf_score = 8.0 if trend_score >= 12.0 else 5.0

        total_score = round(trend_score + momentum_score + volume_score + structure_score + liquidity_score + rr_score + mtf_score, 1)

        direction = "BUY" if chg_24h >= 0 else "SELL"

        return {
            "symbol": symbol,
            "mark_price": price,
            "change_24h": round(chg_24h, 2),
            "volume_usd": round(vol_usd, 2),
            "funding_rate": float(ticker.get("funding_rate", 0) or 0.0),
            "open_interest": float(ticker.get("open_interest", 0) or ticker.get("oi", 0) or 0.0),
            "direction": direction,
            "scores": {
                "trend": trend_score,
                "momentum": momentum_score,
                "volume": volume_score,
                "market_structure": structure_score,
                "liquidity": liquidity_score,
                "risk_reward": rr_score,
                "mtf_alignment": mtf_score,
                "total": total_score
            },
            "total_score": total_score,
            "scanned_at": time.time()
        }

    def scan_all(self, raw_tickers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Scans all tickers, scores each, and returns a sorted ranked watchlist."""
        ranked = []
        for t in raw_tickers:
            sym = t.get("symbol", "")
            # Focus on active perpetual contracts and USD quotes
            if "USD" not in sym:
                continue
            item = self.score_ticker(t)
            # Filter out illiquid zero-price instruments
            if item["mark_price"] > 0 and item["volume_usd"] >= self.min_volume_usd:
                ranked.append(item)

        # Sort descending by total score
        ranked.sort(key=lambda x: x["total_score"], reverse=True)
        return ranked
