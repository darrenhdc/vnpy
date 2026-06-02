# =============================================================================
# 示例策略: MovingAverageCrossStrategy (继承基类)
# =============================================================================
import logging
from typing import Any, Dict, Optional

import numpy as np

from strategies.base_strategy import BaseStrategy
from strategies.registry import StrategyRegistry

logger = logging.getLogger(__name__)


@StrategyRegistry.register("ma_cross")
class MovingAverageCrossStrategy(BaseStrategy):
    """
    双均线交叉策略 (分钟级)。
    短均线上穿长均线 -> 买入信号
    短均线下穿长均线 -> 卖出信号
    只允许 LIMIT 限价单。
    """

    def __init__(self, config, risk_engine, db):
        super().__init__("MovingAverageCrossStrategy", config, risk_engine, db)
        self.short_window: int = config.get("short_window", 5)
        self.long_window: int = config.get("long_window", 20)

    def on_bar_logic(self, symbol: str, bar: Dict[str, Any]) -> Optional[str]:
        bars = self._bars[symbol]
        if len(bars) < self.long_window + 1:
            return None

        closes = [b["close"] for b in bars]
        short_ma = np.mean(closes[-self.short_window:])
        long_ma = np.mean(closes[-self.long_window:])

        prev_short_ma = np.mean(closes[-(self.short_window + 1):-1])
        prev_long_ma = np.mean(closes[-(self.long_window + 1):-1])

        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            return "BUY"
        if prev_short_ma >= prev_long_ma and short_ma < long_ma:
            return "SELL"
        return None

    def get_latest_ma(self, symbol: str) -> Optional[Dict[str, float]]:
        bars = self._bars.get(symbol, [])
        if len(bars) < self.long_window:
            return None
        closes = [b["close"] for b in bars]
        return {
            "short_ma": float(np.mean(closes[-self.short_window:])),
            "long_ma": float(np.mean(closes[-self.long_window:])),
        }

    def _signal_reason(self, symbol: str) -> str:
        ma = self.get_latest_ma(symbol)
        if ma:
            return f"MA{self.short_window}={ma['short_ma']:.2f} cross MA{self.long_window}={ma['long_ma']:.2f}"
        return f"MA{self.short_window}/MA{self.long_window} cross"
