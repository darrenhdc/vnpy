#!/usr/bin/env python3
# =============================================================================
# 无头运行脚本: run_headless.py
# 用于后台运行策略，不启动 GUI。
# =============================================================================
import sys
import time
import signal
import logging
import argparse
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_app_config
from data.database import Database
from risk.risk_engine import RiskEngine
from monitor.healthcheck import HealthChecker
from monitor.notifier import ConsoleNotifier
from strategies.moving_average_cross import MovingAverageCrossStrategy

logger = logging.getLogger("run_headless")


class HeadlessTrader:
    """无头交易运行器。"""

    def __init__(self, strategy_config: dict, futu_config: dict):
        self.db = Database()
        self.db.init_schema()
        self.risk = RiskEngine(self.db)
        self.strategy = MovingAverageCrossStrategy(strategy_config, self.risk, self.db)
        self.health = HealthChecker(
            opend_host=futu_config.get("opend", {}).get("host", "127.0.0.1"),
            opend_port=futu_config.get("opend", {}).get("port", 11111),
            notifier=ConsoleNotifier()
        )
        self._running = False

    def start(self):
        self._running = True
        logger.info("[HeadlessTrader] 启动无头策略运行器")
        # 初次健康检查
        status = self.health.run_full_check(gateway_connected=False)
        if not status.opend_reachable:
            logger.warning("[HeadlessTrader] OpenD 不可达，请确认 Futu OpenD 已启动")
            # 不退出，允许后续重连

        # 模拟运行: 不断从某个源读取 bar（MVP 中可用 mock 或历史数据回放）
        logger.info("[HeadlessTrader] 进入主循环。按 Ctrl+C 停止。")
        try:
            while self._running:
                # MVP: 这里可以接入行情推送或从文件回放 bar
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("[HeadlessTrader] 收到中断信号，正在停止...")
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self.db.close()
        logger.info("[HeadlessTrader] 已停止")

    def on_bar(self, bar: dict):
        """外部行情推送调用此接口。"""
        self.health.update_bar_time()
        self.strategy.on_bar(bar)


def setup_logging():
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"headless_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="无头运行策略")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="覆盖配置中的订阅标的，例如 US.AAPL US.TSLA")
    args = parser.parse_args()

    setup_logging()
    config = get_app_config()
    config.ensure_simulate()

    strategy_cfg = config.strategy.get("moving_average_cross", {})
    if args.symbols:
        strategy_cfg["symbols"] = args.symbols

    trader = HeadlessTrader(strategy_cfg, config.futu)

    # 优雅退出
    def signal_handler(signum, frame):
        logger.info("[main] 收到信号，准备退出...")
        trader.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    trader.start()


if __name__ == "__main__":
    main()
