# =============================================================================
# vnpy MACD 策略 (继承兼容层 CtaTemplate)
# =============================================================================
"""
MACD 动量策略：
- MACD 线 > 信号线 → 多头，买入
- MACD 线 < 信号线 → 卖出平仓
- 只做多 (long-only)

未来 vnpy 安装后，只需改 import：
    from vnpy.app.cta_strategy import CtaTemplate
    from vnpy.trader.object import BarData
"""
import numpy as np
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMacdStrategy(CtaTemplate):
    """
    MACD 动量策略 (12/26/9)。
    金叉买入，死叉卖出。只做多。
    """

    author = "darren"

    fast_period = 12
    slow_period = 26
    signal_period = 9
    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = ["fast_period", "slow_period", "signal_period", "order_amount_usd", "limit_price_offset"]
    variables = ["macd_value", "signal_value", "histogram", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.macd_value: float = 0.0
        self.signal_value: float = 0.0
        self.histogram: float = 0.0
        self.closes: list = []

    def on_init(self):
        super().on_init()
        self.write_log(f"MACD init fast={self.fast_period} slow={self.slow_period} signal={self.signal_period}")

    def on_bar(self, bar: BarData):
        self._bars.append(bar)
        self.closes.append(bar.close_price)

        # 保持足够数据
        max_len = max(self.slow_period, 200)
        if len(self.closes) > max_len:
            self.closes.pop(0)

        if len(self.closes) < self.slow_period:
            return

        # 计算 EMA 和 MACD
        import numpy as np
        closes = np.array(self.closes)
        ema_fast = self._ema(closes, self.fast_period)
        ema_slow = self._ema(closes, self.slow_period)
        macd_line = ema_fast[-1] - ema_slow[-1]

        # 信号线（MACD 的 EMA）
        macd_hist = self._calc_macd_series(closes)
        if len(macd_hist) < self.signal_period:
            return
        signal_line = self._ema(macd_hist, self.signal_period)[-1]

        self.macd_value = macd_line
        self.signal_value = signal_line
        self.histogram = macd_line - signal_line

        # 信号逻辑
        prev_macd = macd_hist[-2] if len(macd_hist) >= 2 else macd_hist[-1]
        prev_signal = self._ema(macd_hist[:-1], self.signal_period)[-1] if len(macd_hist) > self.signal_period else signal_line

        cross_up = (macd_line > signal_line) and (prev_macd <= prev_signal)
        cross_down = (macd_line < signal_line) and (prev_macd >= prev_signal)

        if cross_up and self.pos == 0:
            qty = max(int(self.order_amount_usd / bar.close_price), 1)
            price = bar.close_price + self.limit_price_offset
            self.buy(price, qty)
            self.write_log(f"MACD_CROSS_UP buy {self.symbol} {qty}@{price:.2f} macd={macd_line:.3f} signal={signal_line:.3f}")

        elif cross_down and self.pos > 0:
            price = bar.close_price - self.limit_price_offset
            self.sell(price, abs(self.pos))
            self.write_log(f"MACD_CROSS_DOWN sell {self.symbol} {abs(self.pos)}@{price:.2f} macd={macd_line:.3f} signal={signal_line:.3f}")

    @staticmethod
    def _ema(series: np.ndarray, period: int) -> np.ndarray:
        """计算 EMA 序列。"""
        alpha = 2.0 / (period + 1)
        ema = np.zeros_like(series)
        ema[0] = series[0]
        for i in range(1, len(series)):
            ema[i] = alpha * series[i] + (1 - alpha) * ema[i - 1]
        return ema

    def _calc_macd_series(self, closes: np.ndarray) -> np.ndarray:
        """计算 MACD 线序列（非信号线）。"""
        ema_fast = self._ema(closes, self.fast_period)
        ema_slow = self._ema(closes, self.slow_period)
        return ema_fast - ema_slow
