from datetime import datetime
from zoneinfo import ZoneInfo


def now_ist() -> datetime:
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def format_money(value: float) -> str:
    return f"${value:,.2f}"
