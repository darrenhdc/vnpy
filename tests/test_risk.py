# =============================================================================
# 测试: 风控引擎
# =============================================================================
import sys
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import Database
from risk.risk_engine import RiskEngine


@pytest.fixture
def db():
    db_path = PROJECT_ROOT / "data" / "test.db"
    db = Database(db_path)
    db.init_schema()
    yield db
    db.close()
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def risk(db):
    return RiskEngine(db)


class TestRiskEngine:
    def test_allowed_order_type(self, risk):
        risk.update_market_price("US.AAPL", 150.0)
        # 允许 LIMIT
        res = risk.check_order("US.AAPL", "BUY", "LIMIT", 150.0, 10)
        assert res.approved is True

        # 拒绝 MARKET
        res = risk.check_order("US.AAPL", "BUY", "MARKET", 150.0, 10)
        assert res.approved is False
        assert "订单类型" in res.reason

    def test_max_order_amount(self, risk):
        # 超过 5000 USD 应被拒
        res = risk.check_order("US.AAPL", "BUY", "LIMIT", 600.0, 10)
        assert res.approved is False
        assert "单笔金额" in res.reason

    def test_max_order_quantity(self, risk):
        res = risk.check_order("US.AAPL", "BUY", "LIMIT", 1.0, 200)
        assert res.approved is False
        assert "单笔数量" in res.reason

    def test_no_market_data(self, risk):
        # 未更新价格时下单应被拒
        res = risk.check_order("US.UNKNOWN", "BUY", "LIMIT", 100.0, 1)
        assert res.approved is False
        assert "行情价格" in res.reason

    def test_position_limit(self, risk, db):
        # 先插入一个持仓
        db.insert_position({
            "symbol": "US.AAPL",
            "direction": "LONG",
            "volume": 100,
            "price": 200.0,
            "pnl": 0.0
        })
        risk.update_market_price("US.AAPL", 200.0)
        # 买入 10 股，新的持仓价值 = 100*200 + 10*200 = 22000 > 20000 上限
        res = risk.check_order("US.AAPL", "BUY", "LIMIT", 200.0, 10)
        assert res.approved is False
        assert "持仓金额" in res.reason

    def test_daily_order_count(self, risk, db):
        risk.update_market_price("US.AAPL", 150.0)
        # 假设今日已下 50 单
        for i in range(50):
            db.insert_order({
                "order_id": f"O{i}",
                "symbol": "US.AAPL",
                "direction": "BUY",
                "order_type": "LIMIT",
                "price": 150.0,
                "quantity": 1,
                "status": "SUBMITTED"
            })
        res = risk.check_order("US.AAPL", "BUY", "LIMIT", 150.0, 1)
        assert res.approved is False
        assert "订单数" in res.reason

    def test_signal_cooldown(self, risk):
        risk.update_market_price("US.AAPL", 150.0)
        res1 = risk.check_order("US.AAPL", "BUY", "LIMIT", 150.0, 1)
        assert res1.approved is True
        risk.record_signal("US.AAPL")

        # 立即再次下单应被冷却拦截
        res2 = risk.check_order("US.AAPL", "BUY", "LIMIT", 150.0, 1)
        assert res2.approved is False
        assert "冷却" in res2.reason

    def test_sell_bypass_position_limit(self, risk, db):
        # SELL 不检查单标持仓上限
        db.insert_position({
            "symbol": "US.AAPL",
            "direction": "LONG",
            "volume": 1000,
            "price": 200.0
        })
        risk.update_market_price("US.AAPL", 200.0)
        res = risk.check_order("US.AAPL", "SELL", "LIMIT", 200.0, 10)
        assert res.approved is True
