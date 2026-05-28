# =============================================================================
# 测试: 策略信号生成
# =============================================================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from data.database import Database
from risk.risk_engine import RiskEngine
from strategies.moving_average_cross import MovingAverageCrossStrategy


def build_bar(symbol: str, close: float, timestamp: str = None):
    import datetime
    if timestamp is None:
        timestamp = datetime.datetime.now().isoformat()
    return {
        "symbol": symbol,
        "interval": "1m",
        "timestamp": timestamp,
        "open": close,
        "high": close,
        "low": close,
        "close": close,
        "volume": 100
    }


class TestStrategy:
    def test_ma_cross_signal(self):
        db_path = PROJECT_ROOT / "data" / "test_strategy.db"
        db = Database(db_path)
        db.init_schema()

        risk = RiskEngine(db)
        config = {
            "symbols": ["US.TEST"],
            "interval": "1m",
            "short_window": 3,
            "long_window": 5,
            "quantity": 10,
            "limit_price_offset": 0.01,
            "check_risk_before_order": False  # 测试中关闭风控，专注信号
        }
        strategy = MovingAverageCrossStrategy(config, risk, db)

        # 前 4 根 bar: 价格递减，不足以触发信号
        bars = [
            build_bar("US.TEST", 100.0),
            build_bar("US.TEST", 99.0),
            build_bar("US.TEST", 98.0),
            build_bar("US.TEST", 97.0),
        ]
        for bar in bars:
            strategy.on_bar(bar)
        assert strategy.get_bar_count("US.TEST") == 4

        # 第 5 根 bar: 继续降，长均线形成，无交叉
        strategy.on_bar(build_bar("US.TEST", 96.0))
        assert strategy.get_bar_count("US.TEST") == 5

        # 第 6 根 bar: 价格大涨，短均线上穿长均线 -> BUY
        strategy.on_bar(build_bar("US.TEST", 110.0))
        # 策略内部会写库，这里通过检查信号数量间接验证
        # 因为关闭了风控，应产生订单
        # 我们检查 bar 是否被正确记录
        latest = db.get_latest_bar("US.TEST", "1m")
        assert latest is not None
        assert latest["close"] == 110.0

        # 测试均线数值
        ma = strategy.get_latest_ma("US.TEST")
        assert ma is not None
        assert ma["short_ma"] > ma["long_ma"]

        db.close()
        if db_path.exists():
            db_path.unlink()
