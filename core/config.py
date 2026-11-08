from dataclasses import dataclass, field
from typing import List
from enum import Enum


class TradingMode(str, Enum):
    DEMO = "demo"
    REAL = "real"


@dataclass
class RiskConfig:
    risk_per_trade_pct: float = 0.75
    max_open_positions: int = 4
    max_total_exposure_pct: float = 30.0
    daily_loss_limit_pct: float = 2.8
    weekly_loss_limit_pct: float = 7.5
    min_risk_reward: float = 3.0
    max_leverage_crypto: float = 5.0
    max_leverage_forex: float = 10.0
    max_leverage_indices: float = 10.0


@dataclass
class StrategyConfig:
    # Broader Crypto Universe on Delta Exchange India (Majors + DeFi + Memecoins + Layer 1s)
    crypto_majors: List[str] = field(default_factory=lambda: [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT",
        "ADA/USDT", "AVAX/USDT", "LINK/USDT", "DOGE/USDT", "PEPE/USDT",
        "WIF/USDT", "SHIB/USDT", "SUI/USDT", "NEAR/USDT", "APT/USDT",
        "LDO/USDT", "POPCAT/USDT", "RENDER/USDT", "TAO/USDT", "FET/USDT",
        "ARB/USDT", "OP/USDT", "INJ/USDT", "TIA/USDT", "KAS/USDT"
    ])

    # Traditional assets (via MT5)
    metals: List[str] = field(default_factory=lambda: ["XAUUSD", "XAGUSD"])
    indices: List[str] = field(default_factory=lambda: ["US30", "US100", "SPX"])
    forex_majors: List[str] = field(default_factory=lambda: [
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD"
    ])

    min_consensus_score: float = 0.78
    min_consensus_high_risk: float = 0.88   # memecoins / low liquidity



@dataclass
class ScheduleConfig:
    trade_weekdays: bool = True                 # Mon-Fri
    trade_weekends_247_crypto: bool = True       # Crypto trades 24/7 365 days
    trade_weekends_only_on_strong_flow: bool = False
    high_impact_news_window_minutes: int = 90



@dataclass
class SystemConfig:
    mode: TradingMode = TradingMode.DEMO
    check_interval_seconds: int = 60
    starting_equity: float = 1000.0
    timezone: str = "Asia/Kolkata"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    server_ip: str = "127.0.0.1"

    risk: RiskConfig = field(default_factory=RiskConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)

    # All supported platforms
    enabled_platforms: List[str] = field(default_factory=lambda: [
        "paper",
        "coinbase",
        "delta",
        "coinswitch",
        "myfundedperps",
        "mt5"
    ])
