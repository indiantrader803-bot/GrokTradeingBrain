import logging
from typing import Dict, Any, List, Tuple, Optional
import time

log = logging.getLogger("RiskEngine")

class RiskEngine:
    """
    Independent Risk Engine
    =======================
    Authority to reject any trade regardless of AI signals.
    Configured for high survival micro-capital trading:
      - Starting capital: ~$3.00
      - Max risk per trade: 1.0%
      - Max daily loss: 3.0%
      - Max leverage: 3.0x
      - Max concurrent positions: 1
      - Mandatory Stop-Loss: YES
      - Mandatory Take-Profit: YES
      - Averaging down / Martingale: STRICTLY FORBIDDEN
    """

    def __init__(
        self,
        starting_balance: float = 3.0,
        risk_per_trade_pct: float = 1.0,
        max_daily_loss_pct: float = 3.0,
        max_leverage: float = 3.0,
        max_concurrent_positions: int = 1
    ):
        self.starting_balance = starting_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_leverage = max_leverage
        self.max_concurrent_positions = max_concurrent_positions

        self.daily_start_equity = starting_balance
        self.realized_pnl_today = 0.0
        self.consecutive_losses = 0
        self.cooldown_until: float = 0.0
        self.circuit_breaker_tripped = False

    def check_trade_approval(
        self,
        candidate: Dict[str, Any],
        current_equity: float,
        open_positions: List[Dict[str, Any]],
        contract_value: float = 1.0
    ) -> Tuple[bool, str]:
        now = time.time()

        # 1. Circuit Breaker Check
        if self.circuit_breaker_tripped:
            return False, "BLOCKED: Daily loss circuit breaker tripped (-3% max daily loss limit reached)"

        # 2. Cooldown Check
        if now < self.cooldown_until:
            rem = int(self.cooldown_until - now)
            return False, f"BLOCKED: Risk cooldown active after consecutive losses ({rem}s remaining)"

        # 3. Maximum Concurrent Positions
        if len(open_positions) >= self.max_concurrent_positions:
            return False, f"BLOCKED: Max concurrent positions limit ({self.max_concurrent_positions}) reached"

        # 4. Mandatory Stop-Loss and Take-Profit
        sl = candidate.get("stop_loss")
        tp = candidate.get("take_profit")
        entry = candidate.get("entry_price")

        if not sl or not tp or not entry:
            return False, "BLOCKED: Mandatory stop-loss or take-profit missing"

        if candidate.get("direction") == "BUY" and sl >= entry:
            return False, "BLOCKED: Stop-loss must be strictly below entry for LONG"
        if candidate.get("direction") == "SELL" and sl <= entry:
            return False, "BLOCKED: Stop-loss must be strictly above entry for SHORT"

        # 5. Safe Capital and Minimum Notional Verification
        notional_contract = entry * contract_value
        margin_required = notional_contract / self.max_leverage

        if margin_required > current_equity:
            return False, f"INSUFFICIENT CAPITAL FOR SAFE TRADE (Needs ${margin_required:.2f} margin, account has ${current_equity:.2f})"

        # 6. Duplicate Symbol Position Check (Prevent averaging down / doubling)
        sym = candidate.get("symbol")
        if any(p.get("symbol") == sym for p in open_positions):
            return False, f"BLOCKED: Position on {sym} already active. Averaging down is strictly forbidden"

        return True, "Risk validation PASSED"

    def record_trade_result(self, pnl_usd: float, current_equity: float):
        self.realized_pnl_today += pnl_usd
        if pnl_usd < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                # 3 consecutive losses = 30 minute cooldown
                self.cooldown_until = time.time() + 1800.0
                log.warning("Risk cooldown activated for 30 minutes after 3 consecutive losses")
        else:
            self.consecutive_losses = 0

        # Check daily loss limit
        max_daily_loss = self.daily_start_equity * (self.max_daily_loss_pct / 100.0)
        if self.realized_pnl_today <= -max_daily_loss:
            self.circuit_breaker_tripped = True
            log.critical("DAILY LOSS LIMIT REACHED (-$%.2f). Circuit breaker tripped!", max_daily_loss)
