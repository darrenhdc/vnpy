# =============================================================================
# vnpy MA Cross + RSI 双确认策略
# =============================================================================
"""
逻辑：
- 主信号：MA 金叉/死叉
- 过滤器：RSI 确认不在极端位置

入场（BUY）：fast_ma > slow_ma（金叉）AND RSI < rsi_buy_max
    → 只在 RSI 不过高时追趋势，避免买在山顶

出场（SELL）：fast_ma < slow_ma（死叉）AND RSI > rsi_sell_min
    → 只在 RSI 不过低时止盈，避免割在谷底

未来 vnpy 安装后，只需改 import：
    from vnpy.app.cta_strategy import CtaTemplate
    from vnpy.trader.object import BarData
"""
import numpy as np
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaRsiConfirmStrategy(CtaTemplate):
    """
    MA Cross + RSI 双确认策略。
    金叉确认趋势方向，RSI 过滤极端位置。
    """

    author = "darren"

    fast_window = 5
    slow_window = 15          # SPY 最优参数
    rsi_period = 14
    rsi_buy_max = 50.0        # 买入时 RSI 必须 < 50（不过高）
    rsi_sell_min = 50.0       # 卖出时 RSI 必须 > 50（不过低）
    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = [
        "fast_window", "slow_window",
        "rsi_period", "rsi_buy_max", "rsi_sell_min",
        "order_amount_usd", "limit_price_offset",
    ]
    variables = ["fast_ma_value", "slow_ma_value", "rsi_value", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.fast_ma_value: float = 0.0
        self.slow_ma_value: float = 0.0
        self.rsi_value: float = 50.0
        self.fast_ma: list = []
        self.slow_ma: list = []
        self.closes: list = []

    def on_init(self):
        super().on_init()
        self.write_log(f"MA+RSI Confirm init fast={self.fast_window} slow={self.slow_window} "
                       f"rsi_period={self.rsi_period} buy_max={self.rsi_buy_max} sell_min={self.rsi_sell_min}")

    def on_bar(self, bar: BarData):
        self._bars.append(bar)
        self.closes.append(bar.close_price)

        # 独立维护均线缓存长度
        self.fast_ma.append(bar.close_price)
        self.slow_ma.append(bar.close_price)
        if len(self.fast_ma) > self.fast_window:
            self.fast_ma.pop(0)
        if len(self.slow_ma) > self.slow_window:
            self.slow_ma.pop(0)

        # 数据不足
        if len(self.fast_ma) < self.fast_window or len(self.slow_ma) < self.slow_window:
            return

        self.fast_ma_value = sum(self.fast_ma) / len(self.fast_ma)
        self.slow_ma_value = sum(self.slow_ma) / len(self.slow_ma)

        # 计算 RSI
        if len(self.closes) >= self.rsi_period + 1:
            self.rsi_value = self._calc_rsi(self.closes, self.rsi_period)

        # 信号逻辑：金叉 + RSI 确认
        if self.fast_ma_value > self.slow_ma_value:
            # 金叉 + RSI 不过高 → 买入
            if self.pos == 0 and self.rsi_value < self.rsi_buy_max:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(
                    f"MA+RSI_BUY {self.symbol} {qty}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f} rsi={self.rsi_value:.1f}"
                )
        elif self.fast_ma_value < self.slow_ma_value:
            # 死叉 + RSI 不过低 → 卖出
            if self.pos > 0 and self.rsi_value > self.rsi_sell_min:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(
                    f"MA+RSI_SELL {self.symbol} {abs(self.pos)}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f} rsi={self.rsi_value:.1f}"
                )

    @staticmethod
    def _calc_rsi(closes: list, period: int) -> float:
        if len(closes) < period + 1:
            return 50.0
        arr = np.array(closes)
        deltas = np.diff(arr)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
