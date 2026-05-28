# =============================================================================
# SQLite 数据库模块
# =============================================================================
import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "trading.db"


class Database:
    """SQLite 数据库封装，提供各表初始化和基础写入接口。"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._ensure_dir()
        self.conn: Optional[sqlite3.Connection] = None

    def _ensure_dir(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"[Database] 已连接: {self.db_path}")
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("[Database] 连接已关闭。")

    def init_schema(self):
        """初始化所有表结构。"""
        conn = self.connect()
        cursor = conn.cursor()

        # 1. 行情 K 线
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_bars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, interval, timestamp)
            )
        """)

        # 2. 策略信号
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS strategy_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy_name TEXT NOT NULL,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                price REAL,
                quantity INTEGER,
                reason TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 3. 订单
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                order_type TEXT NOT NULL,
                price REAL,
                quantity INTEGER,
                filled_quantity INTEGER DEFAULT 0,
                status TEXT,
                exchange TEXT,
                account_id TEXT,
                create_time TEXT DEFAULT CURRENT_TIMESTAMP,
                update_time TEXT,
                extra TEXT
            )
        """)

        # 4. 成交
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                order_id TEXT,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                price REAL,
                quantity INTEGER,
                trade_time TEXT,
                exchange TEXT,
                account_id TEXT,
                extra TEXT
            )
        """)

        # 5. 持仓
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL UNIQUE,
                direction TEXT,
                volume INTEGER DEFAULT 0,
                price REAL,
                pnl REAL DEFAULT 0.0,
                yd_volume INTEGER DEFAULT 0,
                update_time TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 6. 账户快照
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                balance REAL,
                available REAL,
                frozen REAL,
                margin REAL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 7. 风控事件
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS risk_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                symbol TEXT,
                description TEXT,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        logger.info("[Database] Schema 初始化完成。")

    # ---------- 写入接口 ----------

    def insert_bar(self, bar: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO market_bars
            (symbol, interval, timestamp, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bar.get("symbol"), bar.get("interval"), bar.get("timestamp"),
            bar.get("open"), bar.get("high"), bar.get("low"),
            bar.get("close"), bar.get("volume")
        ))
        conn.commit()

    def insert_signal(self, signal: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO strategy_signals
            (strategy_name, symbol, signal_type, price, quantity, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            signal.get("strategy_name"), signal.get("symbol"),
            signal.get("signal_type"), signal.get("price"),
            signal.get("quantity"), signal.get("reason")
        ))
        conn.commit()

    def insert_order(self, order: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO orders
            (order_id, symbol, direction, order_type, price, quantity,
             filled_quantity, status, exchange, account_id, update_time, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order.get("order_id"), order.get("symbol"), order.get("direction"),
            order.get("order_type"), order.get("price"), order.get("quantity"),
            order.get("filled_quantity", 0), order.get("status"),
            order.get("exchange"), order.get("account_id"),
            order.get("update_time") or datetime.now().isoformat(),
            json.dumps(order.get("extra", {}))
        ))
        conn.commit()

    def insert_trade(self, trade: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO trades
            (trade_id, order_id, symbol, direction, price, quantity,
             trade_time, exchange, account_id, extra)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade.get("trade_id"), trade.get("order_id"), trade.get("symbol"),
            trade.get("direction"), trade.get("price"), trade.get("quantity"),
            trade.get("trade_time"), trade.get("exchange"),
            trade.get("account_id"), json.dumps(trade.get("extra", {}))
        ))
        conn.commit()

    def insert_position(self, pos: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO positions
            (symbol, direction, volume, price, pnl, yd_volume, update_time)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pos.get("symbol"), pos.get("direction"), pos.get("volume", 0),
            pos.get("price"), pos.get("pnl", 0.0), pos.get("yd_volume", 0),
            datetime.now().isoformat()
        ))
        conn.commit()

    def insert_account_snapshot(self, snapshot: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO account_snapshots
            (account_id, balance, available, frozen, margin)
            VALUES (?, ?, ?, ?, ?)
        """, (
            snapshot.get("account_id"), snapshot.get("balance"),
            snapshot.get("available"), snapshot.get("frozen"),
            snapshot.get("margin")
        ))
        conn.commit()

    def insert_risk_event(self, event: Dict[str, Any]):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO risk_events
            (event_type, symbol, description, details)
            VALUES (?, ?, ?, ?)
        """, (
            event.get("event_type"), event.get("symbol"),
            event.get("description"), json.dumps(event.get("details", {}))
        ))
        conn.commit()

    # ---------- 查询接口 ----------

    def get_today_order_count(self, symbol: Optional[str] = None) -> int:
        """获取今日该标的（或全部）的订单数量。"""
        conn = self.connect()
        cursor = conn.cursor()
        today = datetime.now().strftime("%Y-%m-%d")
        if symbol:
            cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE symbol=? AND create_time LIKE ?",
                (symbol, f"{today}%")
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM orders WHERE create_time LIKE ?",
                (f"{today}%",)
            )
        row = cursor.fetchone()
        return row[0] if row else 0

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions WHERE symbol=?", (symbol,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_all_positions(self) -> List[Dict[str, Any]]:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions")
        return [dict(row) for row in cursor.fetchall()]

    def get_latest_bar(self, symbol: str, interval: str = "1m") -> Optional[Dict[str, Any]]:
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM market_bars WHERE symbol=? AND interval=? ORDER BY timestamp DESC LIMIT 1",
            (symbol, interval)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
