import sqlite3
import json
import time
import os
import logging
from typing import Dict, Any, List, Optional

log = logging.getLogger("Database")

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "trading_platform.db")

def init_db(db_path: str = DB_PATH):
    """Initializes all necessary SQLite tables for persistent platform storage."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. System Config Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at REAL
    )
    """)

    # 2. Market Watchlist & Scores Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS market_watchlist (
        symbol TEXT PRIMARY KEY,
        mark_price REAL,
        change_24h REAL,
        volume_usd REAL,
        funding_rate REAL,
        open_interest REAL,
        trend_score REAL,
        momentum_score REAL,
        volume_score REAL,
        structure_score REAL,
        liquidity_score REAL,
        rr_score REAL,
        mtf_score REAL,
        total_score REAL,
        updated_at REAL
    )
    """)

    # 3. Signals & Committee Decisions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trading_signals (
        id TEXT PRIMARY KEY,
        symbol TEXT,
        direction TEXT,
        strategy TEXT,
        entry_price REAL,
        stop_loss REAL,
        take_profit REAL,
        risk_reward REAL,
        total_score REAL,
        status TEXT, -- APPROVED, REJECTED, EXECUTED, EXPIRED
        rejection_reason TEXT,
        committee_details TEXT, -- JSON blob of all 7 agents
        created_at REAL
    )
    """)

    # 4. Orders Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id TEXT PRIMARY KEY,
        exchange_order_id TEXT,
        symbol TEXT,
        side TEXT,
        size REAL,
        order_type TEXT,
        price REAL,
        stop_loss REAL,
        take_profit REAL,
        status TEXT, -- PENDING, FILLED, CANCELLED, REJECTED
        mode TEXT, -- PAPER or LIVE
        created_at REAL,
        filled_at REAL
    )
    """)

    # 5. Positions Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        id TEXT PRIMARY KEY,
        symbol TEXT,
        side TEXT,
        size REAL,
        entry_price REAL,
        current_price REAL,
        stop_loss REAL,
        take_profit REAL,
        unrealized_pnl REAL,
        realized_pnl REAL,
        margin REAL,
        leverage REAL,
        mode TEXT, -- PAPER or LIVE
        status TEXT, -- OPEN or CLOSED
        opened_at REAL,
        closed_at REAL,
        close_reason TEXT
    )
    """)

    # 6. Trade Journal Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS trade_journal (
        id TEXT PRIMARY KEY,
        symbol TEXT,
        direction TEXT,
        strategy TEXT,
        mode TEXT,
        entry_price REAL,
        exit_price REAL,
        size REAL,
        pnl_usd REAL,
        pnl_pct REAL,
        fees_usd REAL,
        holding_time_sec REAL,
        entry_reason TEXT,
        exit_reason TEXT,
        agent_consensus_score REAL,
        created_at REAL
    )
    """)

    # 7. System Audit Logs Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        level TEXT,
        component TEXT,
        message TEXT,
        metadata TEXT
    )
    """)

    # 8. Insert initial defaults if not present
    defaults = {
        "trading_mode": "PAPER",
        "delta_env": "production",
        "risk_per_trade_pct": "1.0",
        "max_daily_loss_pct": "3.0",
        "max_leverage": "3.0",
        "max_concurrent_positions": "1",
        "starting_balance": "3.0",
        "telegram_enabled": "false",
        "telegram_bot_token": "",
        "telegram_chat_id": ""
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO system_config (key, value, updated_at) VALUES (?, ?, ?)", (k, v, time.time()))

    conn.commit()
    conn.close()
    log.info("SQLite database initialized at: %s", db_path)

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def log_event(level: str, component: str, message: str, metadata: Optional[Dict[str, Any]] = None):
    try:
        conn = get_connection()
        cur = conn.cursor()
        meta_str = json.dumps(metadata) if metadata else ""
        cur.execute("INSERT INTO audit_logs (timestamp, level, component, message, metadata) VALUES (?, ?, ?, ?, ?)",
                    (time.time(), level, component, message, meta_str))
        conn.commit()
        conn.close()
    except Exception as e:
        log.warning("Audit logging error: %s", e)
