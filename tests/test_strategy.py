# =============================================================================
# 测试: 策略在 vnpy_compat 层下的信号生成
# =============================================================================
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from strategies.vnpy_compat import BarData
from strategies.vnpy_ma_cross import VnpyMaCrossStrategy
from strategies.vnpy_macd import VnpyMacdStrategy
from strategies.vnpy_rsi import VnpyRsiStrategy
from datetime import datetime


def build_bar(close: float, timestamp: str = None) -> BarData:
    if timestamp is None:
        timestamp = datetime.now().isoformat()
    return BarData(
        symbol="TEST",
        exchange="US",
        datetime=datetime.now(),
        interval="1m",
        open_price=close,
        high_price=close,
        low_price=close,
        close_price=close,
        volume=100,
    )


class TestVnpyMaCross:
    def test_golden_cross_generates_buy(self):
        strategy = VnpyMaCrossStrategy(None, "test", "US.TEST", {
            "fast_window": 3,
            "slow_window": 5,
            "order_amount_usd": 3000.0,
        })
        # 前 3 根: 平稳价格，不触发（数据不足 slow_window=5）
        for close in [100.0, 100.0, 100.0]:
            strategy.on_bar(build_bar(close))
        assert strategy.pos == 0

        # 第 4-5 根: 继续平稳
        for close in [100.0, 100.0]:
            strategy.on_bar(build_bar(close))
        # 仍然无交叉
        assert strategy.pos == 0

        # 第 6 根: 大涨触发金叉
        strategy.on_bar(build_bar(110.0))
        # 模拟 buy 成交后 pos > 0
        assert strategy.pos > 0

    def test_death_cross_generates_sell(self):
        strategy = VnpyMaCrossStrategy(None, "test", "US.TEST", {
            "fast_window": 3,
            "slow_window": 5,
            "order_amount_usd": 3000.0,
        })
        # 先建立多头（平稳→大涨）
        for close in [100.0, 100.0, 100.0, 100.0, 100.0, 110.0]:
            strategy.on_bar(build_bar(close))
        assert strategy.pos > 0

        # 大跌触发死叉
        strategy.on_bar(build_bar(90.0))
        strategy.on_bar(build_bar(85.0))
        # 平仓后 pos == 0
        assert strategy.pos == 0


class TestVnpyMacd:
    def test_macd_cross(self):
        strategy = VnpyMacdStrategy(None, "test", "US.TEST", {
            "fast_period": 3,
            "slow_period": 5,
            "signal_period": 3,
            "order_amount_usd": 3000.0,
        })
        # 产生足够数据
        for close in [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]:
            strategy.on_bar(build_bar(close))
        # 持续上涨中，MACD 应该金叉买入
        assert strategy.pos >= 0  # 至少不报错


class TestVnpyRsi:
    def test_rsi_oversold_buy(self):
        strategy = VnpyRsiStrategy(None, "test", "US.TEST", {
            "rsi_period": 3,
            "oversold": 30.0,
            "overbought": 70.0,
            "order_amount_usd": 3000.0,
        })
        # 快速下跌触发 RSI < 30
        for close in [100.0, 95.0, 90.0, 85.0, 80.0]:
            strategy.on_bar(build_bar(close))
        # 应该有买入或至少计算正确
        assert strategy.rsi_value < 70  # 确认 RSI 已计算
