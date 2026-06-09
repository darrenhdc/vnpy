# =============================================================================
# vnpy MA 交叉策略 (SOTA v2.3.0 — 13 年逐年 WF 校准)
# =============================================================================
"""
入场: MA(10) > MA(15) 金叉
出场: MA(10) < MA(15) 死叉

OOS: 13 年逐年 Walk-Forward, expanding train / 1y test
     mean Sharpe 0.874, median 1.073, 正收益 10/13 年
     参数 (10/15) 在 11/13 年中一致
"""
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaCrossStrategy(CtaTemplate):
    """
    SOTA v2.3.0 — Pure MA Cross (10/15).
    13 年逐年 WF 验证，OOS mean Sharpe 0.874。
    """

    author = "darren"

    fast_window = 10
    slow_window = 15
    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = ["fast_window", "slow_window", "order_amount_usd", "limit_price_offset"]
    variables = ["fast_ma_value", "slow_ma_value", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.fast_ma_value: float = 0.0
        self.slow_ma_value: float = 0.0
        self.fast_ma: list = []
        self.slow_ma: list = []

    def on_init(self):
        super().on_init()
        self.write_log(f"MA Cross v2.3.0 init fast={self.fast_window} slow={self.slow_window}")

    def on_bar(self, bar: BarData):
        self._bars.append(bar)

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

        if self.fast_ma_value > self.slow_ma_value:
            if self.pos == 0:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(
                    f"GOLDEN_CROSS buy {self.symbol} {qty}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f}"
                )
        elif self.fast_ma_value < self.slow_ma_value:
            if self.pos > 0:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(
                    f"DEATH_CROSS sell {self.symbol} {abs(self.pos)}@{price:.2f}"
                )
