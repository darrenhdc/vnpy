# =============================================================================
# 风控引擎
# =============================================================================
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from config.settings import get_app_config
from data.database import Database

logger = logging.getLogger(__name__)


class RiskCheckResult:
    def __init__(self, approved: bool, reason: str = "", details: Optional[Dict] = None):
        self.approved = approved
        self.reason = reason
        self.details = details or {}

    def __bool__(self):
        return self.approved

    def __repr__(self):
        status = "APPROVED" if self.approved else "REJECTED"
        return f"RiskCheckResult({status}, reason={self.reason})"


class RiskEngine:
    """独立风控模块。策略只能通过 check_order(...) 请求批准。"""

    def __init__(self, db: Database):
        self.config = get_app_config().risk
        self.db = db
        # 信号冷却记录: symbol -> last_signal_datetime
        self._signal_cooldown: Dict[str, datetime] = {}
        # 本地缓存最新价格: symbol -> price
        self._latest_prices: Dict[str, float] = {}
        # 今日订单计数缓存
        self._today_order_count: Optional[int] = None

    def update_market_price(self, symbol: str, price: float):
        """由外部行情推送调用，更新最新价格。"""
        self._latest_prices[symbol] = price

    def check_order(self, symbol: str, direction: str, order_type: str,
                    price: float, quantity: int, strategy_name: str = "",
                    bar_time: Optional[str] = None) -> RiskCheckResult:
        """
        统一订单风控检查。
        direction: "BUY" / "SELL"
        order_type: "LIMIT" / "MARKET" / ...
        """
        enabled = self.config.get("enabled_checks", [])
        details: Dict[str, Any] = {
            "symbol": symbol,
            "direction": direction,
            "order_type": order_type,
            "price": price,
            "quantity": quantity,
            "strategy": strategy_name,
        }

        # 1. 检查订单类型
        if "allowed_order_type" in enabled:
            allowed = self.config.get("single_order", {}).get("allowed_order_types", ["LIMIT"])
            if order_type not in allowed:
                reason = f"订单类型 {order_type} 不在允许列表 {allowed} 中"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 2. 单笔金额限制
        if "max_order_amount" in enabled:
            max_amount = self.config.get("single_order", {}).get("max_order_amount_usd", 999999999)
            order_amount = price * quantity
            if order_amount > max_amount:
                reason = f"单笔金额 {order_amount:.2f} USD 超过上限 {max_amount:.2f} USD"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 3. 单笔数量限制
        if "max_order_quantity" in enabled:
            max_qty = self.config.get("single_order", {}).get("max_order_quantity", 999999999)
            min_qty = self.config.get("single_order", {}).get("min_order_quantity", 1)
            if quantity > max_qty:
                reason = f"单笔数量 {quantity} 超过上限 {max_qty}"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)
            if quantity < min_qty:
                reason = f"单笔数量 {quantity} 低于下限 {min_qty}"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 4. 必须有行情价格
        if "market_data_required" in enabled:
            if symbol not in self._latest_prices or self._latest_prices[symbol] <= 0:
                reason = f"标的 {symbol} 无可用的最新行情价格，禁止下单"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 5. 单标持仓金额限制 (买入时检查)
        if "position_limit" in enabled and direction == "BUY":
            pos_limit = self.config.get("position", {}).get("max_single_position_amount_usd", 999999999)
            pos = self.db.get_position(symbol)
            current_pos_value = 0.0
            if pos and pos.get("volume", 0) > 0:
                current_pos_value = pos.get("volume", 0) * pos.get("price", price)
            new_value = current_pos_value + (price * quantity)
            if new_value > pos_limit:
                reason = f"持仓金额 {new_value:.2f} USD 将超过单标上限 {pos_limit:.2f} USD"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 6. 单日下单次数
        if "daily_order_count" in enabled:
            max_count = self.config.get("daily", {}).get("max_order_count", 999999)
            today_count = self.db.get_today_order_count()
            if today_count >= max_count:
                reason = f"今日订单数 {today_count} 已达上限 {max_count}"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 7. 信号冷却 (防止重复信号)
        if "signal_cooldown" in enabled:
            cooldown_sec = self.config.get("signal", {}).get("cooldown_seconds", 300)
            last_time = self._signal_cooldown.get(symbol)
            # 回测兼容: 如果有 bar_time，使用 bar_time；否则用系统时间
            if bar_time:
                try:
                    current_time = datetime.fromisoformat(bar_time.replace("Z", "+00:00"))
                except Exception:
                    current_time = datetime.now()
            else:
                current_time = datetime.now()
            if last_time and (current_time - last_time).total_seconds() < cooldown_sec:
                reason = f"标的 {symbol} 信号冷却中，距离上次信号仅 {(current_time-last_time).total_seconds():.0f} 秒"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 8. 总持仓数限制 (买入时)
        if "position_limit" in enabled and direction == "BUY":
            max_pos_count = self.config.get("position", {}).get("max_positions_count", 999999)
            all_positions = self.db.get_all_positions()
            # 如果该标的无持仓，则新增一个
            current_symbols = {p["symbol"] for p in all_positions if p.get("volume", 0) != 0}
            has_pos = any(p["symbol"] == symbol and p.get("volume", 0) != 0 for p in all_positions)
            if not has_pos and len(current_symbols) >= max_pos_count:
                reason = f"当前持仓标的数 {len(current_symbols)} 已达上限 {max_pos_count}"
                self._log_rejection(reason, details)
                return RiskCheckResult(False, reason, details)

        # 预留: 单日亏损阈值
        if "daily_loss_limit" in enabled:
            # MVP 中可用 mock equity 或不启用
            pass

        logger.info(f"[RiskEngine] 订单通过风控检查: {symbol} {direction} {quantity}@{price}")
        return RiskCheckResult(True, "approved", details)

    def record_signal(self, symbol: str, bar_time: Optional[str] = None):
        """记录信号触发时间，用于冷却控制。"""
        if bar_time:
            try:
                self._signal_cooldown[symbol] = datetime.fromisoformat(bar_time.replace("Z", "+00:00"))
            except Exception:
                self._signal_cooldown[symbol] = datetime.now()
        else:
            self._signal_cooldown[symbol] = datetime.now()
        logger.info(f"[RiskEngine] 记录 {symbol} 信号时间: {self._signal_cooldown[symbol]}")

    def _log_rejection(self, reason: str, details: Dict[str, Any]):
        logger.warning(f"[RiskEngine] 风控拒单: {reason}")
        self.db.insert_risk_event({
            "event_type": "ORDER_REJECTED",
            "symbol": details.get("symbol"),
            "description": reason,
            "details": details,
        })
