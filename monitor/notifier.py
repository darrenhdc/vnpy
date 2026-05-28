# =============================================================================
# 通知模块
# =============================================================================
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """通知器基类，后续可扩展 Telegram/Email/Webhook。"""

    @abstractmethod
    def send_alert(self, title: str, message: str):
        pass

    @abstractmethod
    def send_info(self, title: str, message: str):
        pass


class ConsoleNotifier(BaseNotifier):
    """控制台通知器（MVP 默认实现）。"""

    def send_alert(self, title: str, message: str):
        print(f"[ALERT] {title}")
        print(message)
        logger.warning(f"[Notifier] ALERT: {title} - {message}")

    def send_info(self, title: str, message: str):
        print(f"[INFO] {title}")
        print(message)
        logger.info(f"[Notifier] INFO: {title} - {message}")
