from core.scanner import MarketScanner
from core.risk_engine import RiskEngine
from core.paper_engine import PaperTradingEngine
from agents.committee import SevenAgentCommittee
from strategies.strategy_modules import StrategyATrendPullback, StrategyCMomentum

def test_scanner_scoring():
    scanner = MarketScanner()
    ticker = {
        "symbol": "BTCUSD",
        "close": 95000.0,
        "change_24h": 6.5,
        "turnover_usd": 750000.0,
        "quotes": {"best_bid": 94990.0, "best_ask": 95010.0}
    }
    score_res = scanner.score_ticker(ticker)
    assert score_res["total_score"] >= 60.0
    assert "scores" in score_res
    assert score_res["direction"] == "BUY"

def test_risk_engine_blocks_insufficient_capital():
    risk = RiskEngine(starting_balance=3.0, max_leverage=3.0)
    # Expensive contract requiring $50 margin on a $3 account
    candidate = {
        "symbol": "BTCUSD",
        "entry_price": 95000.0,
        "stop_loss": 91000.0,
        "take_profit": 105000.0,
        "direction": "BUY"
    }
    # 0.01 BTC notional = $950 -> margin = $316.66 > $3
    allowed, reason = risk.check_trade_approval(candidate, current_equity=3.0, open_positions=[], contract_value=0.01)
    assert not allowed
    assert "INSUFFICIENT CAPITAL" in reason

def test_committee_veto():
    committee = SevenAgentCommittee()
    # Bad setup with tiny volume
    candidate = {
        "symbol": "BADCOINUSD",
        "entry_price": 1.0,
        "stop_loss": 0.95,
        "take_profit": 1.15,
        "direction": "BUY",
        "change_24h": 2.0,
        "volume_usd": 5000.0, # Below $25k -> Skeptic must veto
        "total_score": 65.0
    }
    result = committee.review_candidate(candidate, candles=[], account_equity=3.0, open_positions=[])
    assert not result["approved"]
    assert "Skeptic" in result["reason"]

def test_paper_trading_simulation():
    paper = PaperTradingEngine(starting_capital=10.0)
    pos = paper.open_position("ETHUSD", "BUY", size=1.0, price=3000.0, stop_loss=2900.0, take_profit=3200.0, strategy="Test")
    assert pos["id"] in paper.open_positions

    # Update with profit price
    closed = paper.update_positions({"ETHUSD": 3210.0})
    assert len(closed) == 1
    assert closed[0]["close_reason"] == "TAKE_PROFIT"
    assert paper.capital > 10.0
