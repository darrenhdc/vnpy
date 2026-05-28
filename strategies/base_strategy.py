# =============================================================================
# 策略基类
# =============================================================================
import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from data.database import Database
from risk.risk_engine import RiskEngine

logger = logging.getLogger(__name__)


class BaseStrategy(ABC):
    """
    策略基类。所有具体策略必须继承此类。
    提供统一的 on_bar 入口、资金/持仓管理、盈亏跟踪。
    """

    def __init__(self, name: str, config: Dict[str, Any], risk_engine: RiskEngine, db: Database):
        self.name = name
        self.config = config
        self.risk = risk_engine
        self.db = db

        self.symbols: List[str] = config.get("symbols", [])
        self.interval: str = config.get("interval", "1m")
        self.order_amount_usd: float = config.get("order_amount_usd", 3000.0)
        self.limit_price_offset: float = config.get("limit_price_offset", 0.01)
        self.check_risk: bool = config.get("check_risk_before_order", True)

        # 内部状态
        self._bars: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._positions: Dict[str, Optional[str]] = {s: None for s in self.symbols}
        self._bar_count: Dict[str, int] = defaultdict(int)

    def on_bar(self, bar: Dict[str, Any]):
        """
        统一 K 线入口。
        子类只需实现 on_bar_logic() 生成信号，下单逻辑由基类统一处理。
        """
        symbol = bar.get("symbol")
        if symbol not in self.symbols:
            return

        self._bar_count[symbol] += 1
        self._bars[symbol].append(bar)
        max_len = max(self.config.get("long_window", 20), 100)
        if len(self._bars[symbol]) > max_len:
            self._bars[symbol] = self._bars[symbol][-max_len:]

        # 写入数据库
        self.db.insert_bar(bar)

        # 更新风控价格
        close_price = bar.get("close", 0)
        if close_price > 0:
            self.risk.update_market_price(symbol, close_price)

        # 回测兼容：向风控传入 bar 时间戳
        bar_time = bar.get("timestamp")

        # 子类信号逻辑
        signal = self.on_bar_logic(symbol, bar)
        if signal:
            self._handle_signal(symbol, signal, close_price, bar_time)

    @abstractmethod
    def on_bar_logic(self, symbol: str, bar: Dict[str, Any]) -> Optional[str]:
        """
        子类实现：分析 bar，返回 'BUY' / 'SELL' / None。
        """
        pass

    def _handle_signal(self, symbol: str, signal_type: str, close_price: float, bar_time: Optional[str] = None):
        direction = "BUY" if signal_type == "BUY" else "SELL"

        # 计算下单数量（按金额）
        quantity = self._calculate_quantity(close_price)
        if quantity <= 0:
            logger.info(f"[{self.name}] 金额 {self.order_amount_usd} 不足 1 股，跳过")
            return

        # 记录信号
        self.db.insert_signal({
            "strategy_name": self.name,
            "symbol": symbol,
            "signal_type": signal_type,
            "price": close_price,
            "quantity": quantity,
            "reason": self._signal_reason(symbol)
        })
        logger.info(f"[{self.name}] 产生信号: {symbol} {signal_type} @ {close_price} qty={quantity}")

        # 简单过滤：同向持仓不重复开
        current_pos = self._positions.get(symbol)
        if signal_type == "BUY" and current_pos == "LONG":
            logger.info(f"[{self.name}] 已持有多头，忽略 BUY 信号")
            return
        if signal_type == "SELL" and current_pos == "SHORT":
            logger.info(f"[{self.name}] 已持有空头，忽略 SELL 信号")
            return

        # 风控检查
        if self.check_risk:
            limit_price = self._limit_price(close_price, direction)
            result = self.risk.check_order(
                symbol=symbol,
                direction=direction,
                order_type="LIMIT",
                price=limit_price,
                quantity=quantity,
                strategy_name=self.name,
                bar_time=bar_time,
            )
            if not result.approved:
                logger.warning(f"[{self.name}] 信号 {signal_type} 被风控拦截: {result.reason}")
                return
            self.risk.record_signal(symbol, bar_time)

        self._send_order(symbol, direction, close_price, quantity)

    def _calculate_quantity(self, price: float) -> int:
        """按目标金额计算股数。"""
        if price <= 0:
            return 0
        qty = int(self.order_amount_usd / price)
        return max(qty, 1)

    def _limit_price(self, close_price: float, direction: str) -> float:
        if direction == "BUY":
            return close_price + self.limit_price_offset
        return close_price - self.limit_price_offset

    def _send_order(self, symbol: str, direction: str, close_price: float, quantity: int):
        limit_price = self._limit_price(close_price, direction)
        order_id = f"{symbol.replace('.', '_')}_{datetime.now().strftime('%H%M%S%f')}"

        order = {
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "order_type": "LIMIT",
            "price": round(limit_price, 2),
            "quantity": quantity,
            "status": "SUBMITTED",
            "exchange": "FUTU",
            "account_id": "SIMULATE",
        }
        self.db.insert_order(order)
        logger.info(f"[{self.name}] 提交订单: {direction} {symbol} {quantity}@{limit_price:.2f} (oid={order_id})")

        # 更新本地持仓
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
            "quantity": quantity,
            "trade_time": datetime.now().isoformat(),
            "exchange": "FUTU",
            "account_id": "SIMULATE",
        }
        self.db.insert_trade(trade)
        logger.info(f"[{self.name}] 模拟成交: {direction} {symbol} {quantity}@{limit_price:.2f}")

    @abstractmethod
    def _signal_reason(self, symbol: str) -> str:
        """返回信号产生原因描述。"""
        pass

    def get_bar_count(self, symbol: str) -> int:
        return len(self._bars.get(symbol, []))
