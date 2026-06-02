#!/usr/bin/env python3
# =============================================================================
# 无头实时运行 —— 基于 futu-api 直接连接 OpenD
# =============================================================================
"""
支持所有 vnpy CtaTemplate 兼容策略：
    python scripts/run_live.py --strategy VnpyMaCrossStrategy --symbol US.NVDA
    python scripts/run_live.py --strategy VnpyMacdStrategy --symbol US.SPY
    python scripts/run_live.py --strategy VnpyRsiStrategy --symbol US.QQQ
"""
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
from strategies.vnpy_compat import BarData
from strategies.vnpy_ma_cross import VnpyMaCrossStrategy
from strategies.vnpy_macd import VnpyMacdStrategy
from strategies.vnpy_rsi import VnpyRsiStrategy

logger = logging.getLogger("run_live")

STRATEGY_REGISTRY = {
    "VnpyMaCrossStrategy": VnpyMaCrossStrategy,
    "VnpyMacdStrategy": VnpyMacdStrategy,
    "VnpyRsiStrategy": VnpyRsiStrategy,
}


def setup_logging():
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"live_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def bar_from_futu_row(row: dict) -> BarData:
    """将 futu-api K 线 row 转为 vnpy_compat BarData。"""
    dt = row.get("time_key", "")
    if isinstance(dt, str):
        try:
            dt = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.now()
    return BarData(
        symbol=row.get("code", "").split(".")[-1] if "." in row.get("code", "") else row.get("code", ""),
        exchange="US",
        datetime=dt if isinstance(dt, datetime) else datetime.now(),
        interval="1m",
        open_price=float(row.get("open", 0)),
        high_price=float(row.get("high", 0)),
        low_price=float(row.get("low", 0)),
        close_price=float(row.get("close", 0)),
        volume=float(row.get("volume", 0)),
    )


def run_live(strategy_cls, vt_symbol: str, warmup: int = 100):
    """连接 OpenD，预热历史数据，订阅实时推送。"""
    from futu import OpenQuoteContext, KLType, SubType

    config = get_app_config()
    opend = config.futu.get("opend", {})
    host = opend.get("host", "127.0.0.1")
    port = opend.get("port", 11111)

    symbol = vt_symbol.split(".", 1)[1] if "." in vt_symbol else vt_symbol
    strategy = strategy_cls(
        cta_engine=None,
        strategy_name=strategy_cls.__name__,
        vt_symbol=vt_symbol,
        setting={},
    )

    quote_ctx = OpenQuoteContext(host=host, port=port)

    # 预热历史数据
    logger.info(f"[Live] 预热 {vt_symbol} 历史 {warmup} 条 K 线...")
    ret, data, _ = quote_ctx.request_history_kline(vt_symbol, ktype=KLType.K_1M, max_count=warmup)
    if ret == 0 and not data.empty:
        for _, row in data.iterrows():
            bar = bar_from_futu_row(row.to_dict())
            strategy.on_bar(bar)
        logger.info(f"[Live] 预热完成，缓存 {len(strategy._bars)} 条")
    else:
        logger.warning(f"[Live] 预热失败: {data}")

    # 订阅实时推送
    class KLineHandler:
        def __init__(self, strategy):
            self.strategy = strategy

        def on_recv_rsp(self, rsp_pb):
            from futu import RET_OK
            ret_code, data = rsp_pb
            if ret_code == RET_OK and not data.empty:
                for _, row in data.iterrows():
                    bar = bar_from_futu_row(row.to_dict())
                    self.strategy.on_bar(bar)

    handler = KLineHandler(strategy)
    quote_ctx.set_handler(handler)

    ret, err = quote_ctx.subscribe([vt_symbol], [SubType.K_1M], subscribe_push=True)
    if ret == 0:
        logger.info(f"[Live] 已订阅 {vt_symbol} 实时 1m K 线")
    else:
        logger.error(f"[Live] 订阅失败: {err}")
        quote_ctx.close()
        return

    strategy.on_init()
    strategy.on_start()

    logger.info("[Live] 已进入实时接收状态。按 Ctrl+C 停止。")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("[Live] 收到中断信号...")
    finally:
        strategy.on_stop()
        quote_ctx.close()
        logger.info("[Live] 已停止")


def main():
    parser = argparse.ArgumentParser(description="实时运行策略 (Futu OpenD)")
    parser.add_argument("--strategy", required=True, choices=list(STRATEGY_REGISTRY.keys()),
                        help="策略类名")
    parser.add_argument("--symbol", default="US.SPY",
                        help="标的代码，例如 US.SPY US.QQQ US.NVDA")
    parser.add_argument("--warmup", type=int, default=100,
                        help="预热历史 K 线条数")
    args = parser.parse_args()

    setup_logging()
    config = get_app_config()
    config.ensure_simulate()

    strategy_cls = STRATEGY_REGISTRY[args.strategy]
    run_live(strategy_cls, args.symbol, args.warmup)


if __name__ == "__main__":
    main()
