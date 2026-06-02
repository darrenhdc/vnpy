# =============================================================================
# vnpy RSI 策略 (继承兼容层 CtaTemplate)
# =============================================================================
"""
RSI 逆势策略：
- RSI < oversold (默认 30) → 买入
- RSI > overbought (默认 70) → 卖出 (平仓)
同样只做多。
"""
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyRsiStrategy(CtaTemplate):
    """RSI 逆势做多策略。"""

    author = "darren"

    rsi_period = 14
    oversold = 30.0
    overbought = 70.0
    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = ["rsi_period", "oversold", "overbought", "order_amount_usd", "limit_price_offset"]
    variables = ["rsi_value", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.rsi_value: float = 50.0
        self.closes: list = []

    def on_init(self):
        super().on_init()
        self.write_log(f"RSI init period={self.rsi_period} oversold={self.oversold} overbought={self.overbought}")

    def on_bar(self, bar: BarData):
        self._bars.append(bar)
        self.closes.append(bar.close_price)
        if len(self.closes) > self.rsi_period + 1:
            self.closes.pop(0)

        if len(self.closes) < self.rsi_period + 1:
            return

        self.rsi_value = self._calc_rsi(self.closes, self.rsi_period)

        # 超卖 → 买入
        if self.rsi_value < self.oversold:
            if self.pos == 0:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(f"RSI_OVERSOLD buy {self.symbol} {qty}@{price:.2f} rsi={self.rsi_value:.1f}")

        # 超买 → 卖出
        elif self.rsi_value > self.overbought:
            if self.pos > 0:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(f"RSI_OVERBOUGHT sell {self.symbol} {abs(self.pos)}@{price:.2f} rsi={self.rsi_value:.1f}")

    @staticmethod
    def _calc_rsi(closes: list, period: int) -> float:
        import numpy as np
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))
