# =============================================================================
# 监控与健康检查
# =============================================================================
import logging
import socket
import time
from datetime import datetime
from typing import Dict, Optional

from monitor.notifier import BaseNotifier, ConsoleNotifier

logger = logging.getLogger(__name__)


class HealthStatus:
    def __init__(self):
        self.opend_reachable: bool = False
        self.gateway_connected: bool = False
        self.last_bar_time: Optional[datetime] = None
        self.last_order_update_time: Optional[datetime] = None
        self.errors: list = []

    def is_healthy(self) -> bool:
        return self.opend_reachable and self.gateway_connected

    def summary(self) -> str:
        lines = [
            "=== 健康检查报告 ===",
            f"OpenD 可达:     {self.opend_reachable}",
            f"Gateway 连接:   {self.gateway_connected}",
            f"最近行情时间:   {self.last_bar_time or 'N/A'}",
            f"最近订单时间:   {self.last_order_update_time or 'N/A'}",
        ]
        if self.errors:
            lines.append("错误:")
            for e in self.errors:
                lines.append(f"  - {e}")
        return "\n".join(lines)


class HealthChecker:
    """系统健康检查器。"""

    def __init__(self, opend_host: str = "127.0.0.1", opend_port: int = 11111,
                 notifier: Optional[BaseNotifier] = None):
        self.opend_host = opend_host
        self.opend_port = opend_port
        self.notifier = notifier or ConsoleNotifier()
        self.status = HealthStatus()

    def check_opend(self, timeout: float = 3.0) -> bool:
        """测试 OpenD TCP 端口是否可连接。"""
        try:
            with socket.create_connection((self.opend_host, self.opend_port), timeout=timeout):
                self.status.opend_reachable = True
                return True
        except Exception as e:
            self.status.opend_reachable = False
            self.status.errors.append(f"OpenD 连接失败: {e}")
            logger.warning(f"[HealthChecker] OpenD 不可达: {e}")
            return False

    def check_gateway(self, gateway_connected: bool = False) -> bool:
        """检查 gateway 连接状态（由外部传入）。"""
        self.status.gateway_connected = gateway_connected
        if not gateway_connected:
            self.status.errors.append("Gateway 未连接")
            logger.warning("[HealthChecker] Gateway 未连接")
        return gateway_connected

    def update_bar_time(self):
        self.status.last_bar_time = datetime.now()

    def update_order_time(self):
        self.status.last_order_update_time = datetime.now()

    def check_stale_data(self, max_bar_idle_sec: int = 120, max_order_idle_sec: int = 300) -> bool:
        """检查行情/订单回报是否长时间未更新。"""
        healthy = True
        now = datetime.now()
        if self.status.last_bar_time:
            idle = (now - self.status.last_bar_time).total_seconds()
            if idle > max_bar_idle_sec:
                msg = f"行情已空闲 {idle:.0f} 秒"
                self.status.errors.append(msg)
                logger.warning(f"[HealthChecker] {msg}")
                healthy = False
        if self.status.last_order_update_time:
            idle = (now - self.status.last_order_update_time).total_seconds()
            if idle > max_order_idle_sec:
                msg = f"订单回报已空闲 {idle:.0f} 秒"
                self.status.errors.append(msg)
                logger.warning(f"[HealthChecker] {msg}")
                healthy = False
        return healthy

    def run_full_check(self, gateway_connected: bool = False) -> HealthStatus:
        self.status.errors = []
        self.check_opend()
        self.check_gateway(gateway_connected)
        self.check_stale_data()
        if not self.status.is_healthy():
            self.notifier.send_alert("交易系统健康检查异常", self.status.summary())
        else:
            self.notifier.send_info("健康检查通过", self.status.summary())
        return self.status
