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
from typing import Type

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_app_config
from data.database import Database
from data.live_engine import LiveDataEngine
from risk.risk_engine import RiskEngine
from monitor.healthcheck import HealthChecker
from monitor.notifier import ConsoleNotifier
from strategies import MovingAverageCrossStrategy, RsiStrategy
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger("run_headless")

STRATEGY_REGISTRY = {
    "ma": MovingAverageCrossStrategy,
    "rsi": RsiStrategy,
}


class HeadlessTrader:
    """无头交易运行器。支持 Yahoo 历史回放和 vn.py 实时行情两种模式。"""

    def __init__(self, strategy_cls: Type[BaseStrategy], strategy_config: dict, futu_config: dict):
        self.db = Database()
        self.db.init_schema()
        self.risk = RiskEngine(self.db)
        self.strategy = strategy_cls(strategy_config, self.risk, self.db)
        self.health = HealthChecker(
            opend_host=futu_config.get("opend", {}).get("host", "127.0.0.1"),
            opend_port=futu_config.get("opend", {}).get("port", 11111),
            notifier=ConsoleNotifier()
        )
        self.live_engine: LiveDataEngine = LiveDataEngine(futu_config)
        self._running = False

    def start(self, mode: str = "live"):
        self._running = True
        logger.info(f"[HeadlessTrader] 启动无头策略运行器 mode={mode} strategy={self.strategy.name}")

        status = self.health.run_full_check(gateway_connected=False)
        if not status.opend_reachable:
            logger.warning("[HeadlessTrader] OpenD 不可达，请确认 Futu OpenD 已启动")

        if mode == "live":
            self._run_live()
        else:
            self._run_loop()

    def _run_live(self):
        """连接 vn.py Gateway 接收实时行情。"""
        connected = self.live_engine.connect()
        if connected:
            self.live_engine.register_bar_callback(self._on_bar)
            self.live_engine.subscribe(self.strategy.symbols)
            self.live_engine.run()
        else:
            logger.warning("[HeadlessTrader] 实时连接失败，进入空循环。按 Ctrl+C 停止。")
            self._run_loop()

    def _run_loop(self):
        """空循环（MVP 占位）。"""
        logger.info("[HeadlessTrader] 进入主循环。按 Ctrl+C 停止。")
        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("[HeadlessTrader] 收到中断信号，正在停止...")
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self.live_engine.stop()
        self.db.close()
        logger.info("[HeadlessTrader] 已停止")

    def _on_bar(self, bar: dict):
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
    parser.add_argument("--strategy", default="ma", choices=["ma", "rsi"],
                        help="策略类型: ma (双均线) 或 rsi (默认 ma)")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="覆盖配置中的订阅标的，例如 US.AAPL US.TSLA")
    parser.add_argument("--mode", default="live", choices=["live", "loop"],
                        help="运行模式: live (实时行情) 或 loop (空循环)")
    args = parser.parse_args()

    setup_logging()
    config = get_app_config()
    config.ensure_simulate()

    strategy_cfg = config.strategy.get(args.strategy, {})
    if args.symbols:
        strategy_cfg["symbols"] = args.symbols

    strategy_cls = STRATEGY_REGISTRY[args.strategy]
    trader = HeadlessTrader(strategy_cls, strategy_cfg, config.futu)

    def signal_handler(signum, frame):
        logger.info("[main] 收到信号，准备退出...")
        trader.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    trader.start(mode=args.mode)


if __name__ == "__main__":
    main()
