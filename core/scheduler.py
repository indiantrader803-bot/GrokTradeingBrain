from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from .config import ScheduleConfig

log = logging.getLogger("Scheduler")


class TradingScheduler:
    """
    Controls when the system is allowed to open new trades.

    Rules:
    - Monday to Friday → Trading allowed
    - Saturday & Sunday → Only allowed if strong order flow / high volume
      or high-impact news is detected
    """

    def __init__(self, config: ScheduleConfig, timezone: str = "Asia/Kolkata"):
        self.config = config
        self.tz = ZoneInfo(timezone)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def is_weekday(self) -> bool:
        # Monday = 0 ... Sunday = 6
        return self.now().weekday() < 5

    def is_weekend(self) -> bool:
        return self.now().weekday() >= 5

    def can_trade_now(
        self,
        has_strong_order_flow: bool = False,
        has_high_volume: bool = False,
        has_high_impact_news: bool = False
    ) -> tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str)
        Permits continuous trading across both exchanges today (Saturday) and tomorrow (Sunday).
        """
        if self.config.trade_weekends_247_crypto or self.is_weekday():
            return True, "Trading Active – 24/7 autonomous session across Delta and Coinbase"

        # If weekend trading is explicitly turned off
        if self.is_weekend():
            return False, "Weekend Paused – Next session: Monday morning"

        return True, "Trading Active"

    def get_status(self) -> dict:
        now = self.now()
        return {
            "current_time": now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "weekday": now.strftime("%A"),
            "is_weekday": self.is_weekday(),
            "is_weekend": self.is_weekend(),
        }
