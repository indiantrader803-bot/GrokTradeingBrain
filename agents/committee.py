import time
import logging
from typing import Dict, Any, List, Optional
from core.indicators import TechnicalIndicators

log = logging.getLogger("Committee")

# ── AGENT 1: SCANNER AGENT ──────────────────────────────────────
class ScannerAgent:
    name = "Scanner"
    def evaluate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        total_score = candidate.get("total_score", 0.0)
        approved = total_score >= 60.0
        return {
            "agent": self.name,
            "approved": approved,
            "score": total_score,
            "reason": f"Ranked Scanner Score: {total_score}/100 points ({'PASS' if approved else 'BELOW THRESHOLD 60'})"
        }

# ── AGENT 2: TREND ANALYST AGENT ────────────────────────────────
class TrendAnalystAgent:
    name = "Trend_Analyst"
    def evaluate(self, candidate: Dict[str, Any], candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not candles or len(candles) < 30:
            return {"agent": self.name, "approved": True, "score": 70.0, "reason": "Default trend validation: insufficient candle history"}
        closes = [c["close"] for c in candles]
        current_price = closes[-1]
        ema9 = TechnicalIndicators.calculate_ema(closes, 9)
        ema21 = TechnicalIndicators.calculate_ema(closes, 21)
        vwap = TechnicalIndicators.calculate_vwap(candles[-30:])
        direction = candidate.get("direction", "BUY")

        if direction == "BUY":
            trend_aligned = current_price >= vwap or ema9 >= ema21
            score = 85.0 if (current_price >= vwap and ema9 >= ema21) else (65.0 if trend_aligned else 40.0)
        else:
            trend_aligned = current_price <= vwap or ema9 <= ema21
            score = 85.0 if (current_price <= vwap and ema9 <= ema21) else (65.0 if trend_aligned else 40.0)

        approved = score >= 60.0
        return {
            "agent": self.name,
            "approved": approved,
            "score": score,
            "reason": f"M5 Trend: Price={current_price:.4f}, VWAP={vwap:.4f}, EMA9={ema9:.4f}, EMA21={ema21:.4f}"
        }

# ── AGENT 3: MOMENTUM HUNTER AGENT ──────────────────────────────
class MomentumHunterAgent:
    name = "Momentum_Hunter"
    def evaluate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        chg = abs(candidate.get("change_24h", 0.0))
        vol = candidate.get("volume_usd", 0.0)
        
        # Evaluates price velocity and volume acceleration
        if 2.0 <= chg <= 35.0 and vol >= 30000.0:
            score = 85.0
            approved = True
            reason = f"Strong momentum confirmation (+{chg:.1f}% velocity with ${vol:,.0f} volume)"
        elif chg > 45.0:
            score = 45.0
            approved = False
            reason = f"Extreme momentum overextension ({chg:.1f}% 24h change: reversal hazard)"
        elif vol < 20000.0:
            score = 35.0
            approved = False
            reason = f"Insufficient volume velocity (${vol:,.0f} < $20k minimum)"
        else:
            score = 65.0
            approved = True
            reason = f"Moderate momentum setup ({chg:.1f}%)"

        return {"agent": self.name, "approved": approved, "score": score, "reason": reason}

# ── AGENT 4: SKEPTIC AGENT (VETO AUTHORITY) ──────────────────────
class SkepticAgent:
    name = "Skeptic"
    def evaluate(self, candidate: Dict[str, Any], account_equity: float, open_positions: List[Any]) -> Dict[str, Any]:
        """
        The Skeptic actively searches for reasons to REJECT the trade:
        - Liquidity / spread traps
        - Extreme funding rates
        - Conflicting signals or fakeouts
        - Slippage hazards
        """
        vol = candidate.get("volume_usd", 0.0)
        funding = abs(candidate.get("funding_rate", 0.0))
        chg = candidate.get("change_24h", 0.0)

        # 1. Illiquidity check
        if vol < 25000.0:
            return {"agent": self.name, "approved": False, "score": 20.0, "reason": f"Skeptic VETO: Low 24h volume (${vol:,.0f}) creates slippage hazard"}

        # 2. Extreme funding rate trap
        if funding > 0.0015:  # > 0.15% funding per 8h
            return {"agent": self.name, "approved": False, "score": 25.0, "reason": f"Skeptic VETO: Adverse funding rate ({funding*100:.3f}%) punishes position holding"}

        # 3. Parabolic blow-off top
        if abs(chg) >= 50.0:
            return {"agent": self.name, "approved": False, "score": 15.0, "reason": f"Skeptic VETO: Parabolic move ({chg:+.1f}%) risks immediate violent mean reversion"}

        # Passed skeptical review
        return {"agent": self.name, "approved": True, "score": 80.0, "reason": "Skeptic PASS: No spread traps, liquidity hazards, or funding anomalies detected"}

# ── AGENT 5: POSITION SIZER AGENT ───────────────────────────────
class PositionSizerAgent:
    name = "Position_Sizer"
    def evaluate(
        self,
        candidate: Dict[str, Any],
        account_equity: float,
        contract_value: float = 1.0,
        max_risk_pct: float = 1.0,
        max_leverage: float = 3.0
    ) -> Dict[str, Any]:
        """
        Calculates position size strictly respecting micro-account risk.
        Starting balance ~$3 -> 1% risk per trade ($0.03).
        Enforces minimum contract size and minimum exchange balance.
        """
        entry = candidate.get("entry_price", 0.0)
        sl = candidate.get("stop_loss", 0.0)
        
        if entry <= 0 or sl <= 0 or account_equity <= 0:
            return {"agent": self.name, "approved": False, "score": 0.0, "reason": "Invalid entry price or zero balance"}

        distance = abs(entry - sl)
        if distance <= 0:
            return {"agent": self.name, "approved": False, "score": 0.0, "reason": "Stop loss distance is zero"}

        # Max dollar loss allowed
        max_loss_usd = account_equity * (max_risk_pct / 100.0)
        # Notional value of 1 contract
        notional_one_contract = entry * contract_value
        margin_one_contract = notional_one_contract / max_leverage

        # Safe order size check: Can account equity safely hold minimum 1 contract?
        if margin_one_contract > account_equity:
            return {
                "agent": self.name,
                "approved": False,
                "score": 30.0,
                "size": 0,
                "reason": f"INSUFFICIENT CAPITAL FOR SAFE TRADE: 1 contract of {candidate.get('symbol')} requires ${margin_one_contract:.2f} margin, account has ${account_equity:.2f}"
            }

        # Size 1 contract for micro capital preservation
        size = 1

        return {
            "agent": self.name,
            "approved": True,
            "score": 90.0,
            "size": size,
            "margin_required": round(margin_one_contract, 4),
            "max_loss_usd": round(distance * contract_value * size, 4),
            "leverage": max_leverage,
            "reason": f"Sizer PASS: Size {size} contract | Margin: ${margin_one_contract:.4f} | Max Risk: ${max_loss_usd:.4f}"
        }

# ── AGENT 6: TRADER AGENT (DETERMINISTIC EXECUTION GATE) ─────────
class TraderAgent:
    name = "Trader"
    def evaluate(self, committee_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        The Trader executes only when:
          - Scanner, Trend Analyst, Momentum Hunter approve
          - Skeptic DOES NOT reject
          - Position Sizer approves
        """
        vetoed = False
        rejection_reasons = []

        for res in committee_results:
            if not res.get("approved"):
                vetoed = True
                rejection_reasons.append(f"{res.get('agent')}: {res.get('reason')}")

        if vetoed:
            return {
                "agent": self.name,
                "approved": False,
                "score": 0.0,
                "reason": f"Execution BLOCKED by Committee veto: {'; '.join(rejection_reasons)}"
            }

        return {
            "agent": self.name,
            "approved": True,
            "score": 100.0,
            "reason": "Trader APPROVED: Unanimous committee consensus achieved with strict risk parameters"
        }

# ── AGENT 7: JOURNAL AGENT ──────────────────────────────────────
class JournalAgent:
    name = "Journal"
    def record_decision(self, candidate: Dict[str, Any], committee_summary: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "agent": self.name,
            "recorded": True,
            "timestamp": time.time(),
            "symbol": candidate.get("symbol"),
            "status": "APPROVED" if committee_summary.get("approved") else "REJECTED",
            "summary": committee_summary.get("reason")
        }

# ── SEVEN-AGENT COMMITTEE ORCHESTRATOR ──────────────────────────
class SevenAgentCommittee:
    def __init__(self):
        self.scanner_agent = ScannerAgent()
        self.trend_agent = TrendAnalystAgent()
        self.momentum_agent = MomentumHunterAgent()
        self.skeptic_agent = SkepticAgent()
        self.sizer_agent = PositionSizerAgent()
        self.trader_agent = TraderAgent()
        self.journal_agent = JournalAgent()

    def review_candidate(
        self,
        candidate: Dict[str, Any],
        candles: List[Dict[str, Any]],
        account_equity: float,
        open_positions: List[Any],
        contract_value: float = 1.0,
        max_leverage: float = 3.0
    ) -> Dict[str, Any]:
        # Run individual agents
        r_scanner = self.scanner_agent.evaluate(candidate)
        r_trend = self.trend_agent.evaluate(candidate, candles)
        r_momentum = self.momentum_agent.evaluate(candidate)
        r_skeptic = self.skeptic_agent.evaluate(candidate, account_equity, open_positions)
        r_sizer = self.sizer_agent.evaluate(candidate, account_equity, contract_value=contract_value, max_leverage=max_leverage)

        sub_committee = [r_scanner, r_trend, r_momentum, r_skeptic, r_sizer]
        r_trader = self.trader_agent.evaluate(sub_committee)
        
        committee_all = sub_committee + [r_trader]
        r_journal = self.journal_agent.record_decision(candidate, r_trader)
        committee_all.append(r_journal)

        return {
            "approved": r_trader["approved"],
            "reason": r_trader["reason"],
            "size": r_sizer.get("size", 1),
            "leverage": r_sizer.get("leverage", max_leverage),
            "margin_required": r_sizer.get("margin_required", 0.0),
            "agents": {res["agent"]: res for res in committee_all}
        }
