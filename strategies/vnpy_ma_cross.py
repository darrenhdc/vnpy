# =============================================================================
# vnpy MA 交叉 + RSI 卖出过滤器策略 (SOTA v2.4.0)
# =============================================================================
"""
入场: MA(10) > MA(15) 金叉
出场: MA(10) < MA(15) 死叉 AND RSI(14) > 50

OOS: 13 年逐年 WF, expanding train / 1y test
     mean Sharpe 1.112, 正收益 11/13 年
     参数 (10/15/50) 在 13/13 年中一致
"""
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaCrossStrategy(CtaTemplate):
    """
    SOTA v2.4.0 — MA Cross + RSI SellFilter (sell_min=50).
    金叉即买，死叉+RSI>50才卖。
    """

    author = "darren"

    fast_window = 10
    slow_window = 15
    rsi_period = 14
    rsi_sell_min = 50
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
        self.write_log(
            f"MA+RSI v2.4.0 init fast={self.fast_window} slow={self.slow_window} "
            f"rsi={self.rsi_period}/{self.rsi_sell_min}"
        )

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

        # RSI
        if len(self.closes) >= self.rsi_period + 1:
            self.rsi_value = self._calc_rsi()

        # Entry: golden cross → buy (no filter)
        if self.fast_ma_value > self.slow_ma_value:
            if self.pos == 0:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(
                    f"MA_BUY {self.symbol} {qty}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f} rsi={self.rsi_value:.1f}"
                )

        # Exit: death cross + RSI > sell_min → sell
        elif self.fast_ma_value < self.slow_ma_value:
            if self.pos > 0 and self.rsi_value > self.rsi_sell_min:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(
                    f"MA+RSI_SELL {self.symbol} {abs(self.pos)}@{price:.2f} "
                    f"rsi={self.rsi_value:.1f}"
                )

    def _calc_rsi(self) -> float:
        if len(self.closes) < self.rsi_period + 1:
            return 50.0
        gains = 0.0; losses = 0.0
        recent = self.closes[-(self.rsi_period + 1):]
        for i in range(1, len(recent)):
            delta = recent[i] - recent[i-1]
            if delta > 0: gains += delta
            else: losses -= delta
        avg_gain = gains / self.rsi_period
        avg_loss = losses / self.rsi_period
        if avg_loss == 0: return 100.0
        return 100.0 - (100.0 / (1.0 + avg_gain / avg_loss))
