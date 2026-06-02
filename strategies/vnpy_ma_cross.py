# =============================================================================
# vnpy MA 交叉策略 (继承兼容层 CtaTemplate)
# =============================================================================
"""
未来 vnpy 安装后，只需把:
    from strategies.vnpy_compat import CtaTemplate, BarData
改为:
    from vnpy.app.cta_strategy import CtaTemplate
    from vnpy.trader.object import BarData
"""
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaCrossStrategy(CtaTemplate):
    """
    双均线交叉策略。
    fast_ma > slow_ma → buy
    fast_ma < slow_ma → sell (平仓)
    只做多 (long-only)，适配美股现货账户。
    """

    author = "darren"

    # 策略参数 —— vnpy 用它们做 GUI 绑定
    fast_window = 5
    slow_window = 20
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
        self.write_log(f"MA Cross init fast={self.fast_window} slow={self.slow_window}")

    def on_bar(self, bar: BarData):
        """接收新 K 线。"""
        self._bars.append(bar)

        # 更新均线缓存（fast 和 slow 独立维护长度）
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
        self.slow_ma_value = sum(self.slow_ma[-self.slow_window:]) / self.slow_window

        # 信号逻辑：金叉买入，死叉卖出
        if self.fast_ma_value > self.slow_ma_value:
            if self.pos == 0:
                qty = max(int(self.order_amount_usd / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(f"GOLDEN_CROSS buy {self.symbol} {qty}@{price:.2f} fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f}")
        elif self.fast_ma_value < self.slow_ma_value:
            if self.pos > 0:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(f"DEATH_CROSS sell {self.symbol} {abs(self.pos)}@{price:.2f} fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f}")
