#!/usr/bin/env python3
# =============================================================================
# 启动脚本: run_trader.py
# 用于启动 vn.py GUI 或最小交易入口。
# =============================================================================
import sys
import argparse
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import get_app_config
from data.database import Database
from risk.risk_engine import RiskEngine
from monitor.healthcheck import HealthChecker
from monitor.notifier import ConsoleNotifier
from strategies.moving_average_cross import MovingAverageCrossStrategy

# vn.py 相关 (如果已安装)
try:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine
    from vnpy.trader.ui import MainWindow, create_qapp
    from vnpy_futu import FutuGateway
    VNPY_AVAILABLE = True
except ImportError:
    VNPY_AVAILABLE = False
    print("[Warning] vn.py / vnpy_futu 未安装，将以最小模式运行。")


def setup_logging():
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"trader_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def run_minimal(config):
    """最小模式: 不依赖 vn.py GUI，直接运行策略逻辑（适合无头测试）。"""
    from datetime import datetime
    print("[run_trader] 以最小模式启动 (无 GUI)")
    db = Database()
    db.init_schema()
    risk = RiskEngine(db)
    health = HealthChecker(
        opend_host=config.futu.get("opend", {}).get("host", "127.0.0.1"),
        opend_port=config.futu.get("opend", {}).get("port", 11111),
        notifier=ConsoleNotifier()
    )
    status = health.run_full_check(gateway_connected=False)
    print(status.summary())
    print("[run_trader] 最小模式启动完成。如需运行策略请使用 run_headless.py")


def run_vnpy_gui(config):
    """启动 vn.py GUI + FutuGateway。"""
    if not VNPY_AVAILABLE:
        print("[Error] vn.py 未安装，无法启动 GUI。请安装 vnpy 和 vnpy_futu。")
        sys.exit(1)

    app = create_qapp()
    event_engine = EventEngine()
    main_engine = MainEngine(event_engine)
    main_engine.add_gateway(FutuGateway)

    # 配置 FutuGateway
    opend_cfg = config.futu.get("opend", {})
    setting = {
        "address": opend_cfg.get("host", "127.0.0.1"),
        "port": str(opend_cfg.get("port", 11111)),
        "password": config.futu.get("trade_password", ""),
        "env": config.futu.get("environment", "SIMULATE"),
    }

    print(f"[run_trader] 正在连接 Futu OpenD: {setting['address']}:{setting['port']}")
    print(f"[run_trader] 环境: {setting['env']}")

    try:
        main_engine.connect(setting, "FUTU")
    except Exception as e:
        print(f"[run_trader] 连接 Gateway 失败: {e}")
        sys.exit(1)

    main_window = MainWindow(main_engine, event_engine)
    main_window.showMaximized()
    app.exec()


def main():
    parser = argparse.ArgumentParser(description="启动美股量化交易系统")
    parser.add_argument("--mode", choices=["gui", "minimal"], default="minimal",
                        help="启动模式: gui (vn.py GUI) 或 minimal (最小入口)")
    args = parser.parse_args()

    setup_logging()
    config = get_app_config()
    config.ensure_simulate()

    logger = logging.getLogger(__name__)
    logger.info(f"[run_trader] 启动模式: {args.mode}, 环境: {config.futu.get('environment')}")

    if args.mode == "gui":
        run_vnpy_gui(config)
    else:
        run_minimal(config)


if __name__ == "__main__":
    from datetime import datetime
    main()
