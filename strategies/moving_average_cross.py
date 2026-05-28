# =============================================================================
# 示例策略: MovingAverageCrossStrategy
# =============================================================================
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from data.database import Database
from risk.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class MovingAverageCrossStrategy:
    """
    双均线交叉策略 (分钟级)。
    短均线上穿长均线 -> 买入信号
    短均线下穿长均线 -> 卖出信号
    只允许 LIMIT 限价单。
    """

    def __init__(self, config: Dict[str, Any], risk_engine: RiskEngine, db: Database):
        self.name = "MovingAverageCrossStrategy"
        self.config = config
        self.risk = risk_engine
        self.db = db

        self.symbols: List[str] = config.get("symbols", ["US.AAPL"])
        self.interval: str = config.get("interval", "1m")
        self.short_window: int = config.get("short_window", 5)
        self.long_window: int = config.get("long_window", 20)
        self.quantity: int = config.get("quantity", 10)
        self.limit_price_offset: float = config.get("limit_price_offset", 0.01)
        self.check_risk: bool = config.get("check_risk_before_order", True)

        # 每个标的的 K 线缓存
        self._bars: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        # 当前持仓方向缓存: symbol -> "LONG" / "SHORT" / None
        self._positions: Dict[str, Optional[str]] = {s: None for s in self.symbols}

    def on_bar(self, bar: Dict[str, Any]):
        """接收新 K 线并处理。"""
        symbol = bar.get("symbol")
        if symbol not in self.symbols:
            return

        # 更新本地缓存
        self._bars[symbol].append(bar)
        # 限制缓存长度
        max_len = max(self.long_window, 100)
        if len(self._bars[symbol]) > max_len:
            self._bars[symbol] = self._bars[symbol][-max_len:]

        # 写入数据库
        self.db.insert_bar(bar)

        # 更新风控价格
        close_price = bar.get("close", 0)
        if close_price > 0:
            self.risk.update_market_price(symbol, close_price)

        # 检查是否有足够数据计算均线
        if len(self._bars[symbol]) < self.long_window:
            logger.debug(f"[{self.name}] {symbol} 数据不足 ({len(self._bars[symbol])}/{self.long_window})")
            return

        signal = self._calculate_signal(symbol)
        if signal:
            self._handle_signal(symbol, signal, close_price)

    def _calculate_signal(self, symbol: str) -> Optional[str]:
        """计算双均线交叉信号。返回 'BUY', 'SELL' 或 None。"""
        bars = self._bars[symbol]
        closes = [b["close"] for b in bars]

        # 计算均线
        short_ma = np.mean(closes[-self.short_window:])
        long_ma = np.mean(closes[-self.long_window:])

        # 前一根 K 线的均线
        if len(closes) >= self.long_window + 1:
            prev_short_ma = np.mean(closes[-(self.short_window + 1):-1])
            prev_long_ma = np.mean(closes[-(self.long_window + 1):-1])
        else:
            return None

        # 金叉: 短均线上穿长均线
        if prev_short_ma <= prev_long_ma and short_ma > long_ma:
            return "BUY"

        # 死叉: 短均线下穿长均线
        if prev_short_ma >= prev_long_ma and short_ma < long_ma:
            return "SELL"

        return None

    def _handle_signal(self, symbol: str, signal_type: str, close_price: float):
        """处理交易信号。"""
        direction = "BUY" if signal_type == "BUY" else "SELL"

        # 记录信号
        self.db.insert_signal({
            "strategy_name": self.name,
            "symbol": symbol,
            "signal_type": signal_type,
            "price": close_price,
            "quantity": self.quantity,
            "reason": f"MA{self.short_window}/MA{self.long_window} cross"
        })
        logger.info(f"[{self.name}] 产生信号: {symbol} {signal_type} @ {close_price}")

        # 简单过滤: 已有同向持仓不再重复开
        current_pos = self._positions.get(symbol)
        if signal_type == "BUY" and current_pos == "LONG":
            logger.info(f"[{self.name}] 已持有多头，忽略 BUY 信号")
            return
        if signal_type == "SELL" and current_pos == "SHORT":
            logger.info(f"[{self.name}] 已持有空头，忽略 SELL 信号")
            return

        # 风控检查
        if self.check_risk:
            # 限价单价格: 买入时略高，卖出时略低，增加成交概率
            if signal_type == "BUY":
                limit_price = close_price + self.limit_price_offset
            else:
                limit_price = close_price - self.limit_price_offset

            result = self.risk.check_order(
                symbol=symbol,
                direction=direction,
                order_type="LIMIT",
                price=limit_price,
                quantity=self.quantity,
                strategy_name=self.name
            )
            if not result.approved:
                logger.warning(
                    f"[{self.name}] 信号 {signal_type} 被风控拦截: {result.reason}"
                )
                return
            # 通过风控，记录信号时间（用于冷却）
            self.risk.record_signal(symbol)

        # 模拟下单
        self._send_order(symbol, direction, close_price)

    def _send_order(self, symbol: str, direction: str, close_price: float):
        """发送限价单（MVP 中为模拟/日志记录）。"""
        if direction == "BUY":
            limit_price = close_price + self.limit_price_offset
        else:
            limit_price = close_price - self.limit_price_offset

        order_id = f"{symbol.replace('.', '_')}_{datetime.now().strftime('%H%M%S%f')}"

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "order_type": "LIMIT",
            "price": round(limit_price, 2),
            "quantity": self.quantity,
            "status": "SUBMITTED",
            "exchange": "FUTU",
            "account_id": "SIMULATE",
        }
        self.db.insert_order(order)
        logger.info(f"[{self.name}] 提交订单: {direction} {symbol} {self.quantity}@{limit_price:.2f} (oid={order_id})")

        # 更新本地持仓状态 (MVP 简化: 直接假设成交)
        if direction == "BUY":
            self._positions[symbol] = "LONG"
        else:
            self._positions[symbol] = "SHORT"

        # 记录成交
        trade = {
            "trade_id": f"T_{order_id}",
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "price": round(limit_price, 2),
            "quantity": self.quantity,
            "trade_time": datetime.now().isoformat(),
            "exchange": "FUTU",
            "account_id": "SIMULATE",
        }
        self.db.insert_trade(trade)
        logger.info(f"[{self.name}] 模拟成交: {direction} {symbol} {self.quantity}@{limit_price:.2f}")

    def get_bar_count(self, symbol: str) -> int:
        return len(self._bars.get(symbol, []))

    def get_latest_ma(self, symbol: str) -> Optional[Dict[str, float]]:
        bars = self._bars.get(symbol, [])
        if len(bars) < self.long_window:
            return None
        closes = [b["close"] for b in bars]
        return {
            "short_ma": float(np.mean(closes[-self.short_window:])),
            "long_ma": float(np.mean(closes[-self.long_window:])),
        }
