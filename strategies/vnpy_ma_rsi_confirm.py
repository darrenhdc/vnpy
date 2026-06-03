# =============================================================================
# vnpy MA Cross + RSI 卖出过滤器 + ATR 仓位管理 策略
# =============================================================================
"""
逻辑（基于 SPY 参数搜索 + WF 验证所得最优架构）：

入场（BUY）：fast_ma > slow_ma（金叉），无 RSI 过滤
    → 金叉是趋势信号，不应被 RSI 条件延迟。

出场（SELL）：fast_ma < slow_ma（死叉）AND RSI > rsi_sell_min
    → 超卖（RSI < 40）时的死叉是假信号，延迟卖出捕捉反弹。

ATR 仓位管理：
    ATR > 1.5x 中位数 → 极端高波动，缩仓至 33%（减仓避险）
    ATR < 0.8x 中位数 → 极端低波动，扩仓至 2.0x（低波动加仓）
    否则 → 正常仓位

回测结果（SPY 5y, order_size=30%）:
    v1.2.0 (无ATR):    Sharpe=1.456  Ret=+27.0%  MaxDD=-4.4%
    v1.3.0 (+ATR):     Sharpe=1.626  Ret=+27.7%  MaxDD=-3.3%  (+11.7%/+25%)
    WF Holdout: 2.096（无退化）
"""
import numpy as np
from strategies.vnpy_compat import CtaTemplate, BarData


class VnpyMaRsiConfirmStrategy(CtaTemplate):
    """
    MA Cross + RSI 卖出过滤 + ATR 仓位管理策略。
    """

    author = "darren"

    # MA
    fast_window = 5
    slow_window = 15
    # RSI
    rsi_period = 14
    rsi_sell_min = 40
    # ATR
    atr_period = 14
    atr_hi_thr = 1.5            # ATR > 1.5x 中位数 → 高波动缩仓
    atr_lo_thr = 0.8            # ATR < 0.8x 中位数 → 低波动扩仓
    atr_hi_mult = 0.33          # 高波动仓位系数
    atr_lo_mult = 2.0           # 低波动仓位系数
    atr_median_lookback = 252   # ATR 中位数回看周期

    order_amount_usd = 3000.0
    limit_price_offset = 0.01

    parameters = [
        "fast_window", "slow_window",
        "rsi_period", "rsi_sell_min",
        "atr_period", "atr_hi_thr", "atr_lo_thr", "atr_hi_mult", "atr_lo_mult",
        "order_amount_usd", "limit_price_offset",
    ]
    variables = ["fast_ma_value", "slow_ma_value", "rsi_value", "atr_value", "atr_median", "pos"]

    def __init__(self, cta_engine, strategy_name, vt_symbol, setting):
        super().__init__(cta_engine, strategy_name, vt_symbol, setting)
        self.fast_ma_value: float = 0.0
        self.slow_ma_value: float = 0.0
        self.rsi_value: float = 50.0
        self.atr_value: float = 0.0
        self.atr_median: float = 0.0
        self.fast_ma: list = []
        self.slow_ma: list = []
        self.closes: list = []
        self.highs: list = []
        self.lows: list = []
        self.tr_list: list = []

    def on_init(self):
        super().on_init()
        self.write_log(
            f"MA+RSI+ATR init fast={self.fast_window} slow={self.slow_window} "
            f"rsi={self.rsi_period}/{self.rsi_sell_min} "
            f"atr={self.atr_period} hi={self.atr_hi_thr}/{self.atr_hi_mult} lo={self.atr_lo_thr}/{self.atr_lo_mult}"
        )

    def on_bar(self, bar: BarData):
        self._bars.append(bar)
        self.closes.append(bar.close_price)
        self.highs.append(bar.high_price)
        self.lows.append(bar.low_price)

        # === MA 计算 ===
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

        # === RSI 计算 ===
        if len(self.closes) >= self.rsi_period + 1:
            self.rsi_value = self._calc_rsi(self.closes, self.rsi_period)

        # === ATR 计算 ===
        if len(self.closes) >= 2:
            tr = max(
                self.highs[-1] - self.lows[-1],
                abs(self.highs[-1] - self.closes[-2]),
                abs(self.lows[-1] - self.closes[-2]),
            )
            self.tr_list.append(tr)
            if len(self.tr_list) > self.atr_median_lookback:
                self.tr_list.pop(0)
            if len(self.tr_list) >= self.atr_period:
                self.atr_value = sum(self.tr_list[-self.atr_period:]) / self.atr_period
                if len(self.tr_list) >= 63:
                    self.atr_median = float(np.median(self.tr_list[-self.atr_median_lookback:]))

        # === ATR 仓位系数 ===
        position_mult = 1.0
        if hasattr(self, "atr_median") and self.atr_median is not None and self.atr_value > 0 and self.atr_median > 0:
            ratio = self.atr_value / self.atr_median
            if ratio > self.atr_hi_thr:
                position_mult = self.atr_hi_mult
            elif ratio < self.atr_lo_thr:
                position_mult = self.atr_lo_mult

        adj_amount = self.order_amount_usd * position_mult

        # === 信号执行 ===
        if self.fast_ma_value > self.slow_ma_value:
            if self.pos == 0:
                qty = max(int(adj_amount / bar.close_price), 1)
                price = bar.close_price + self.limit_price_offset
                self.buy(price, qty)
                self.write_log(
                    f"MA_BUY {self.symbol} {qty}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f} "
                    f"rsi={self.rsi_value:.1f} atr={self.atr_value:.2f}"
                )
        elif self.fast_ma_value < self.slow_ma_value:
            if self.pos > 0 and self.rsi_value > self.rsi_sell_min:
                price = bar.close_price - self.limit_price_offset
                self.sell(price, abs(self.pos))
                self.write_log(
                    f"MA+RSI_SELL {self.symbol} {abs(self.pos)}@{price:.2f} "
                    f"fast={self.fast_ma_value:.2f} slow={self.slow_ma_value:.2f} "
                    f"rsi={self.rsi_value:.1f} atr={self.atr_value:.2f}"
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
