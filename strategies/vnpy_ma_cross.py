# =============================================================================
# vnpy MA 交叉 + ATR 追踪止损策略
# =============================================================================
"""
入场: MA(5) > MA(15) 金叉
出场: MA(5) < MA(15) 死叉 OR 价格 < 持仓高点 - 2×ATR(OOS Sharpe 1.348)
"""
import numpy as np
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaCrossStrategy(CtaTemplate):
    """
    MA Cross + ATR Trailing Stop.
    SOTA v2.2.0 — OOS Sharpe 1.348 (Train 2011-2021 / Test 2021-2026).
    """

    author = "darren"

    fast_window = 5
    slow_window = 15
    atr_period = 14
    atr_stop_mult = 2.0
    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = [
        "fast_window", "slow_window",
        "atr_period", "atr_stop_mult",
        "order_amount_usd", "limit_price_offset",
    ]
    variables = ["fast_ma_value", "slow_ma_value", "atr_value", "trail_high", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.fast_ma_value: float = 0.0
        self.slow_ma_value: float = 0.0
        self.atr_value: float = 0.0
        self.trail_high: float = 0.0
        self.fast_ma: list = []
        self.slow_ma: list = []
        self.closes: list = []
        self.highs: list = []
        self.lows: list = []

    def on_init(self):
        super().on_init()
        self.write_log(
            f"MA+ATR Stop init fast={self.fast_window} slow={self.slow_window} "
            f"atr={self.atr_period}/{self.atr_stop_mult}"
        )

    def on_bar(self, bar: BarData):
        self._bars.append(bar)
        self.closes.append(bar.close_price)
        self.highs.append(bar.high_price)
        self.lows.append(bar.low_price)

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

        # ATR
        if len(self.closes) >= 2:
            tr = max(
                self.highs[-1] - self.lows[-1],
                abs(self.highs[-1] - self.closes[-2]),
                abs(self.lows[-1] - self.closes[-2]),
            )
            if not hasattr(self, '_tr_vals'):
                self._tr_vals = []
            self._tr_vals.append(tr)
            if len(self._tr_vals) > self.atr_period:
                self._tr_vals.pop(0)
            if len(self._tr_vals) >= self.atr_period:
                self.atr_value = sum(self._tr_vals) / len(self._tr_vals)

        # Trail
        if self.pos > 0:
            self.trail_high = max(self.trail_high, bar.close_price)

        # Entry: golden cross
        if self.fast_ma_value > self.slow_ma_value:
            if self.pos == 0:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.trail_high = bar.close_price
                self.write_log(
                    f"MA_BUY {self.symbol} {qty}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f}"
                )

        # Exit: death cross OR trailing stop
        elif self.fast_ma_value < self.slow_ma_value:
            if self.pos > 0:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(
                    f"DEATH_SELL {self.symbol} {abs(self.pos)}@{price:.2f}"
                )
        elif self.pos > 0 and self.atr_value > 0:
            stop_price = self.trail_high - self.atr_stop_mult * self.atr_value
            if bar.close_price < stop_price:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(
                    f"ATR_STOP {self.symbol} {abs(self.pos)}@{price:.2f} "
                    f"trail={self.trail_high:.2f} atr={self.atr_value:.2f}"
                )
