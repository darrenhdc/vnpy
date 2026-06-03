# =============================================================================
# vnpy MA Cross + RSI 卖出过滤器策略
# =============================================================================
"""
逻辑（基于 SPY 参数搜索 + WF 验证得出的最优架构）：

入场（BUY）：fast_ma > slow_ma（金叉），无 RSI 过滤
    → 金叉是趋势信号，不应被 RSI 条件延迟。错过金叉比追高风险更大。

出场（SELL）：fast_ma < slow_ma（死叉）AND RSI > rsi_sell_min
    → 只在 RSI 不在超卖区时才卖。市场上升趋势中，死叉常发生在短暂回调
      导致的超卖（RSI < 40）。此时不应卖，应等待反弹。

回测结果（SPY 5y, order_size=30%）:
    Sharpe=1.456 (SOTA=1.337, +8.9%)
    Return=+27.0% (SOTA=+22.5%)
    MaxDD=-4.4%
    WF Holdout Sharpe=2.096
"""
import numpy as np
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaRsiConfirmStrategy(CtaTemplate):
    """
    MA Cross + RSI 卖出过滤策略。
    金叉即买，死叉 + RSI > 阈值才卖。
    """

    author = "darren"

    fast_window = 5
    slow_window = 15          # SPY 最优参数
    rsi_period = 14
    rsi_sell_min = 40         # 死叉时 RSI 必须 > 40 才卖（避免割在超卖）
    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = [
        "fast_window", "slow_window",
        "rsi_period", "rsi_sell_min",
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
        self.write_log(f"MA+RSI SellFilter init fast={self.fast_window} slow={self.slow_window} "
                       f"rsi_period={self.rsi_period} sell_min={self.rsi_sell_min}")

    def on_bar(self, bar: BarData):
        self._bars.append(bar)
        self.closes.append(bar.close_price)

        self.fast_ma.append(bar.close_price)
        self.slow_ma.append(bar.close_price)
        if len(self.fast_ma) > self.fast_window:
            self.fast_ma.pop(0)
        if len(self.slow_ma) > self.slow_window:
            self.slow_ma.pop(0)

        if len(self.fast_ma) < self.fast_window or len(self.slow_ma) < self.slow_window:
            return

        self.fast_ma_value = sum(self.fast_ma) / len(self.fast_ma)
        self.slow_ma_value = sum(self.slow_ma) / len(self.slow_ma)

        if len(self.closes) >= self.rsi_period + 1:
            self.rsi_value = self._calc_rsi(self.closes, self.rsi_period)

        # BUY: 金叉即买（不过滤）
        if self.fast_ma_value > self.slow_ma_value:
            if self.pos == 0:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(
                    f"MA_BUY {self.symbol} {qty}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f} rsi={self.rsi_value:.1f}"
                )
        # SELL: 死叉 + RSI > sell_min 才卖（避免割在超卖区）
        elif self.fast_ma_value < self.slow_ma_value:
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
