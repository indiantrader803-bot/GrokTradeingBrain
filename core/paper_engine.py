import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from core.database import get_connection

log = logging.getLogger("PaperEngine")

class PaperTradingEngine:
    """
    Paper Trading Simulation Engine
    ===============================
    Executes trades in virtual memory + SQLite with:
      - Realistic taker fee simulation (0.05%)
      - Realistic market slippage (0.05%)
      - Real market price execution
      - Live P&L and Stop-Loss / Take-Profit tracking
    """

    def __init__(self, starting_capital: float = 3.0):
        self.capital = starting_capital
        self.open_positions: Dict[str, Dict[str, Any]] = {}
        self.closed_trades: List[Dict[str, Any]] = []

    def open_position(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        stop_loss: float,
        take_profit: float,
        strategy: str,
        leverage: float = 3.0,
        contract_value: float = 1.0
    ) -> Dict[str, Any]:
        # Apply 0.05% slippage on entry
        slippage = 0.0005
        exec_price = price * (1.0 + slippage) if side == "BUY" else price * (1.0 - slippage)
        fee = exec_price * contract_value * size * 0.0005

        pos_id = str(uuid.uuid4())[:8]
        margin = (exec_price * contract_value * size) / leverage

        position = {
            "id": pos_id,
            "symbol": symbol,
            "side": side,
            "size": size,
            "entry_price": round(exec_price, 6),
            "current_price": round(exec_price, 6),
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "margin": round(margin, 4),
            "leverage": leverage,
            "strategy": strategy,
            "fee": round(fee, 6),
            "opened_at": time.time(),
            "mode": "PAPER"
        }

        self.open_positions[pos_id] = position
        self.capital -= fee

        # Persist to SQLite
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO positions (id, symbol, side, size, entry_price, current_price, stop_loss, take_profit,
                                   unrealized_pnl, realized_pnl, margin, leverage, mode, status, opened_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0.0, 0.0, ?, ?, 'PAPER', 'OPEN', ?)
            """, (pos_id, symbol, side, size, exec_price, exec_price, stop_loss, take_profit, margin, leverage, time.time()))
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("Paper position save error: %s", e)

        log.info("PAPER POSITION OPENED: %s %s @ $%.4f (Margin: $%.4f, Fee: $%.4f)", side, symbol, exec_price, margin, fee)
        return position

    def update_positions(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        closed_this_tick = []
        for pos_id, pos in list(self.open_positions.items()):
            cur_price = current_prices.get(pos["symbol"])
            if not cur_price or cur_price <= 0:
                continue

            pos["current_price"] = cur_price
            side = pos["side"]
            entry = pos["entry_price"]
            size = pos["size"]
            sl = pos["stop_loss"]
            tp = pos["take_profit"]

            if side == "BUY":
                pnl = (cur_price - entry) * size
                pos["unrealized_pnl"] = round(pnl, 4)
                if cur_price <= sl:
                    closed = self._close_position(pos_id, cur_price, "STOP_LOSS")
                    closed_this_tick.append(closed)
                elif cur_price >= tp:
                    closed = self._close_position(pos_id, cur_price, "TAKE_PROFIT")
                    closed_this_tick.append(closed)
            else:
                pnl = (entry - cur_price) * size
                pos["unrealized_pnl"] = round(pnl, 4)
                if cur_price >= sl:
                    closed = self._close_position(pos_id, cur_price, "STOP_LOSS")
                    closed_this_tick.append(closed)
                elif cur_price <= tp:
                    closed = self._close_position(pos_id, cur_price, "TAKE_PROFIT")
                    closed_this_tick.append(closed)

        return closed_this_tick

    def _close_position(self, pos_id: str, exit_price: float, reason: str) -> Dict[str, Any]:
        pos = self.open_positions.pop(pos_id, None)
        if not pos:
            return {}

        side = pos["side"]
        entry = pos["entry_price"]
        size = pos["size"]
        fee = exit_price * size * 0.0005
        raw_pnl = (exit_price - entry) * size if side == "BUY" else (entry - exit_price) * size
        net_pnl = round(raw_pnl - fee, 4)
        pnl_pct = round((net_pnl / pos["margin"]) * 100.0, 2) if pos["margin"] > 0 else 0.0

        self.capital += net_pnl
        pos["closed_at"] = time.time()
        pos["exit_price"] = exit_price
        pos["realized_pnl"] = net_pnl
        pos["close_reason"] = reason

        self.closed_trades.append(pos)

        # Update SQLite
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
            UPDATE positions SET current_price = ?, realized_pnl = ?, status = 'CLOSED', closed_at = ?, close_reason = ?
            WHERE id = ?
            """, (exit_price, net_pnl, time.time(), reason, pos_id))

            # Insert into Journal
            cur.execute("""
            INSERT INTO trade_journal (id, symbol, direction, strategy, mode, entry_price, exit_price, size,
                                       pnl_usd, pnl_pct, fees_usd, holding_time_sec, entry_reason, exit_reason, created_at)
            VALUES (?, ?, ?, ?, 'PAPER', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4())[:8], pos["symbol"], pos["side"], pos["strategy"], entry, exit_price, size,
                  net_pnl, pnl_pct, fee, time.time() - pos["opened_at"], "Committee Consensus", reason, time.time()))
            conn.commit()
            conn.close()
        except Exception as e:
            log.warning("Paper position close error: %s", e)

        log.info("PAPER POSITION CLOSED: %s %s @ $%.4f | Reason: %s | Net PnL: $%.4f (%+.1f%%)",
                 pos["side"], pos["symbol"], exit_price, reason, net_pnl, pnl_pct)
        return pos
