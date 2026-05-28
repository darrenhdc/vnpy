# =============================================================================
# 测试: 数据库与 Schema
# =============================================================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import Database


class TestDatabase:
    def test_init_schema_and_crud(self):
        db_path = PROJECT_ROOT / "data" / "test_crud.db"
        db = Database(db_path)
        db.init_schema()

        # insert bar
        db.insert_bar({
            "symbol": "US.AAPL",
            "interval": "1m",
            "timestamp": "2024-01-01T09:30:00",
            "open": 150.0,
            "high": 151.0,
            "low": 149.5,
            "close": 150.5,
            "volume": 1000
        })
        bar = db.get_latest_bar("US.AAPL", "1m")
        assert bar is not None
        assert bar["close"] == 150.5

        # insert signal
        db.insert_signal({
            "strategy_name": "Test",
            "symbol": "US.AAPL",
            "signal_type": "BUY",
            "price": 150.5,
            "quantity": 10,
            "reason": "test"
        })

        # insert order
        db.insert_order({
            "order_id": "O1",
            "symbol": "US.AAPL",
            "direction": "BUY",
            "order_type": "LIMIT",
            "price": 150.5,
            "quantity": 10,
            "status": "FILLED"
        })
        assert db.get_today_order_count("US.AAPL") >= 1

        # insert position
        db.insert_position({
            "symbol": "US.AAPL",
            "direction": "LONG",
            "volume": 10,
            "price": 150.5,
            "pnl": 0.0
        })
        pos = db.get_position("US.AAPL")
        assert pos is not None
        assert pos["volume"] == 10

        db.close()
        if db_path.exists():
            db_path.unlink()
