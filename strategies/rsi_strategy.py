# =============================================================================
# RSI 策略
# =============================================================================
import logging
from typing import Any, Dict, List, Optional

import numpy as np

from strategies.base_strategy import BaseStrategy

logger = logging.getLogger(__name__)


class RsiStrategy(BaseStrategy):
    """
    RSI (相对强弱指数) 策略。
    RSI < oversold (默认 30) -> 买入
    RSI > overbought (默认 70) -> 卖出
    只允许 LIMIT 限价单。
    """

    def __init__(self, config, risk_engine, db):
        super().__init__("RsiStrategy", config, risk_engine, db)
        self.rsi_period: int = config.get("rsi_period", 14)
        self.oversold: float = config.get("oversold", 30.0)
        self.overbought: float = config.get("overbought", 70.0)

    def on_bar_logic(self, symbol: str, bar: Dict[str, Any]) -> Optional[str]:
        bars = self._bars[symbol]
        if len(bars) < self.rsi_period + 1:
            return None

        closes = np.array([b["close"] for b in bars])
        rsi = self._calculate_rsi(closes, self.rsi_period)

        if rsi is None:
            return None

        # 上穿超卖线 -> BUY
        if rsi < self.oversold:
            return "BUY"
        # 下穿超买线 -> SELL
        if rsi > self.overbought:
            return "SELL"
        return None

    def _calculate_rsi(self, closes: np.ndarray, period: int) -> Optional[float]:
        if len(closes) < period + 1:
            return None
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi)

    def _signal_reason(self, symbol: str) -> str:
        bars = self._bars.get(symbol, [])
        if len(bars) < self.rsi_period + 1:
            return "RSI insufficient data"
        closes = np.array([b["close"] for b in bars])
        rsi = self._calculate_rsi(closes, self.rsi_period)
        return f"RSI({self.rsi_period})={rsi:.1f}"
