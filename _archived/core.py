# =============================================================================
# 共享决策核心 —— 策略间可复用的信号/特征/状态组件
# =============================================================================
"""
core.py 提供与具体策略无关的通用决策组件：
- FeatureEngine: 统一特征计算（MA, RSI, MACD, ATR, Volume）
- SignalBuffer: 信号去重/平滑/延时确认
- StateTracker: 多策略共享的持仓/盈亏状态

使用示例:
    from strategies.core import FeatureEngine, SignalBuffer
    feats = FeatureEngine(bars_df)
    ma_cross = feats.golden_cross(short=5, long=20)
    sig_buf = SignalBuffer(cooldown_bars=3)
    if sig_buf.push("US.AAPL", ma_cross):
        # 真正执行
"""
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FeatureEngine:
    """基于 pandas DataFrame 的统一特征引擎。"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.close = df["close"]

    # ---------- 均线 ----------
    def ma(self, window: int) -> pd.Series:
        return self.close.rolling(window, min_periods=1).mean()

    def ema(self, span: int) -> pd.Series:
        return self.close.ewm(span=span, adjust=False).mean()

    def golden_cross(self, short: int, long: int) -> pd.Series:
        """短均线上穿长均线，返回 bool Series。"""
        s = self.ma(short)
        l = self.ma(long)
        return (s > l) & (s.shift(1) <= l.shift(1))

    def death_cross(self, short: int, long: int) -> pd.Series:
        s = self.ma(short)
        l = self.ma(long)
        return (s < l) & (s.shift(1) >= l.shift(1))

    # ---------- RSI ----------
    def rsi(self, period: int = 14) -> pd.Series:
        delta = self.close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        return 100.0 - (100.0 / (1.0 + rs))

    # ---------- MACD ----------
    def macd(self, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = self.ema(fast)
        ema_slow = self.ema(slow)
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        hist = macd_line - signal_line
        return macd_line, signal_line, hist

    def macd_cross_up(self, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.Series:
        macd_line, signal_line, _ = self.macd(fast, slow, signal)
        return (macd_line > signal_line) & (macd_line.shift(1) <= signal_line.shift(1))

    # ---------- ATR / Volatility ----------
    def atr(self, period: int = 14) -> pd.Series:
        h = self.df["high"]
        l = self.df["low"]
        c = self.close
        tr = pd.concat([
            (h - l).abs(),
            (h - c.shift(1)).abs(),
            (l - c.shift(1)).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(alpha=1 / period, adjust=False).mean()

    def rolling_volatility(self, window: int = 20, annualize: bool = True) -> pd.Series:
        ret = self.close.pct_change()
        vol = ret.rolling(window, min_periods=5).std()
        if annualize:
            vol = vol * np.sqrt(252)
        return vol

    # ---------- Volume ----------
    def volume_ma(self, window: int = 20) -> pd.Series:
        return self.df["volume"].rolling(window, min_periods=1).mean()

    def volume_ratio(self, window: int = 20) -> pd.Series:
        return self.df["volume"] / self.volume_ma(window)


class SignalBuffer:
    """
    信号缓冲器：防止同一标的在短时间内反复触发。
    支持 cooldown（冷却条数）和 confirmation（确认条数）。
    """

    def __init__(self, cooldown_bars: int = 3, confirmation_bars: int = 0):
        self.cooldown = cooldown_bars
        self.confirmation = confirmation_bars
        self._last_bar: Dict[str, int] = {}
        self._pending: Dict[str, Tuple[str, int]] = {}  # symbol -> (signal_type, start_bar)

    def push(self, symbol: str, signal_type: str, bar_index: int) -> bool:
        """
        推送原始信号。
        如果 signal_type 与 pending 不同，重置 pending。
        如果 confirmation_bars > 0，需要连续 confirmation_bars 次相同信号才通过。
        通过后的信号受 cooldown 限制。
        """
        # cooldown 检查
        if symbol in self._last_bar:
            if bar_index - self._last_bar[symbol] < self.cooldown:
                return False

        # confirmation 逻辑
        if self.confirmation > 0:
            pending = self._pending.get(symbol)
            if pending is None or pending[0] != signal_type:
                self._pending[symbol] = (signal_type, bar_index)
                return False
            start_idx = pending[1]
            if bar_index - start_idx + 1 < self.confirmation:
                return False
            # 确认通过，清除 pending
            del self._pending[symbol]

        self._last_bar[symbol] = bar_index
        return True

    def reset(self, symbol: str):
        self._last_bar.pop(symbol, None)
        self._pending.pop(symbol, None)


@dataclass
class StateTracker:
    """
    多策略共享的持仓与盈亏状态。
    可持久化到 SQLite，也可仅内存运行。
    """

    # symbol -> {"direction": "LONG"/"SHORT", "entry_price": float, "volume": int}
    positions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # 按交易对记录盈亏
    closed_trades: List[Dict[str, Any]] = field(default_factory=list)

    def open_position(self, symbol: str, direction: str, price: float, volume: int):
        self.positions[symbol] = {
            "direction": direction,
            "entry_price": price,
            "volume": volume,
            "opened_at": None,
        }

    def close_position(self, symbol: str, exit_price: float) -> Optional[Dict[str, Any]]:
        pos = self.positions.pop(symbol, None)
        if not pos:
            return None
        pnl = 0.0
        if pos["direction"] == "LONG":
            pnl = (exit_price - pos["entry_price"]) * pos["volume"]
        else:
            pnl = (pos["entry_price"] - exit_price) * pos["volume"]
        trade = {
            "symbol": symbol,
            "direction": pos["direction"],
            "entry_price": pos["entry_price"],
            "exit_price": exit_price,
            "volume": pos["volume"],
            "pnl": round(pnl, 2),
        }
        self.closed_trades.append(trade)
        return trade

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        return self.positions.get(symbol)

    def total_pnl(self) -> float:
        return sum(t["pnl"] for t in self.closed_trades)

    def win_rate(self) -> float:
        if not self.closed_trades:
            return 0.0
        wins = sum(1 for t in self.closed_trades if t["pnl"] > 0)
        return wins / len(self.closed_trades)
