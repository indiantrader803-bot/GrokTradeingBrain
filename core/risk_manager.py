from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, date
import logging

from .config import RiskConfig

log = logging.getLogger("RiskManager")


@dataclass
class Position:
    id: str
    symbol: str
    platform: str
    side: str                    # BUY or SELL
    size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    risk_amount: float
    opened_at: datetime = field(default_factory=datetime.utcnow)
    asset_class: str = "crypto"


class RiskManager:
    def __init__(self, config: RiskConfig, starting_equity: float):
        self.config = config
        self.equity = starting_equity
        self.open_positions: List[Position] = []
        self.daily_pnl: float = 0.0
        self.weekly_pnl: float = 0.0
        self.current_day: date = datetime.utcnow().date()
        self.current_week = datetime.utcnow().isocalendar()[1]

    def update_equity(self, new_equity: float):
        self.equity = max(new_equity, 0.0)

    def _reset_period_if_needed(self):
        today = datetime.utcnow().date()
        week = datetime.utcnow().isocalendar()[1]

        if today != self.current_day:
            self.daily_pnl = 0.0
            self.current_day = today
            log.info("Daily PnL reset")

        if week != self.current_week:
            self.weekly_pnl = 0.0
            self.current_week = week
            log.info("Weekly PnL reset")

    def can_open_new_position(self, risk_amount: float) -> tuple[bool, str]:
        self._reset_period_if_needed()

        if len(self.open_positions) >= self.config.max_open_positions:
            return False, "Max open positions reached"

        total_risk = sum(p.risk_amount for p in self.open_positions) + risk_amount
        exposure_pct = (total_risk / self.equity) * 100 if self.equity > 0 else 100
        if exposure_pct > self.config.max_total_exposure_pct:
            return False, f"Total exposure limit exceeded ({exposure_pct:.1f}%)"

        daily_limit = self.equity * (self.config.daily_loss_limit_pct / 100)
        if self.daily_pnl <= -daily_limit:
            return False, "Daily loss limit reached"

        weekly_limit = self.equity * (self.config.weekly_loss_limit_pct / 100)
        if self.weekly_pnl <= -weekly_limit:
            return False, "Weekly loss limit reached"

        return True, "OK"

    def calculate_position_size(self, entry: float, stop_loss: float) -> float:
        if entry <= 0 or stop_loss <= 0:
            return 0.0

        risk_capital = self.equity * (self.config.risk_per_trade_pct / 100)
        distance = abs(entry - stop_loss)

        if distance == 0:
            return 0.0

        size = risk_capital / distance
        return round(size, 6)

    def register_position(self, position: Position):
        self.open_positions.append(position)
        log.info(
            "Position registered | %s %s | Size: %.6f | Risk: %.2f",
            position.side, position.symbol, position.size, position.risk_amount
        )

    def close_position(self, position_id: str, pnl: float):
        self.open_positions = [p for p in self.open_positions if p.id != position_id]
        self.daily_pnl += pnl
        self.weekly_pnl += pnl
        log.info("Position closed | ID: %s | PnL: %.2f | Daily PnL: %.2f", position_id, pnl, self.daily_pnl)

    def get_open_positions(self) -> List[Position]:
        return list(self.open_positions)

    def get_status(self) -> dict:
        self._reset_period_if_needed()
        return {
            "equity": round(self.equity, 2),
            "open_positions": len(self.open_positions),
            "daily_pnl": round(self.daily_pnl, 2),
            "weekly_pnl": round(self.weekly_pnl, 2),
            "daily_loss_limit": round(self.equity * self.config.daily_loss_limit_pct / 100, 2),
            "weekly_loss_limit": round(self.equity * self.config.weekly_loss_limit_pct / 100, 2),
        }
