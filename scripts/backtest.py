#!/usr/bin/env python3
# =============================================================================
# 回测脚本: 使用 Yahoo Finance 历史数据回放策略
# =============================================================================
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Type

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

from config.settings import get_app_config
from data.database import Database
from data.yahoo_feeder import fetch_bars
from risk.risk_engine import RiskEngine
from strategies import MovingAverageCrossStrategy, RsiStrategy
from strategies.base_strategy import BaseStrategy

logger = logging.getLogger("backtest")

STRATEGY_REGISTRY = {
    "ma": MovingAverageCrossStrategy,
    "rsi": RsiStrategy,
}


class PerformanceAnalyzer:
    """基于数据库订单和成交记录计算回测指标。"""

    def __init__(self, db: Database):
        self.db = db

    def analyze(self) -> Dict[str, Any]:
        conn = self.db.connect()
        cursor = conn.cursor()

        # 1. 信号统计
        cursor.execute("SELECT COUNT(*) FROM strategy_signals")
        total_signals = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM strategy_signals WHERE signal_type='BUY'")
        buy_signals = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM strategy_signals WHERE signal_type='SELL'")
        sell_signals = cursor.fetchone()[0]

        # 2. 成交统计
        cursor.execute("SELECT COUNT(*), SUM(quantity), AVG(price) FROM trades")
        row = cursor.fetchone()
        total_trades = row[0] or 0
        total_shares = row[1] or 0
        avg_trade_price = row[2] or 0.0

        cursor.execute("SELECT COUNT(*) FROM trades WHERE direction='BUY'")
        buy_trades = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM trades WHERE direction='SELL'")
        sell_trades = cursor.fetchone()[0] or 0

        # 3. 持仓
        cursor.execute("SELECT * FROM positions")
        positions = [dict(r) for r in cursor.fetchall()]

        # 4. 风控拦截统计
        cursor.execute("SELECT COUNT(*) FROM risk_events WHERE event_type='ORDER_REJECTED'")
        risk_rejects = cursor.fetchone()[0] or 0

        # 5. 盈亏计算 (简化 FIFO)
        cursor.execute("SELECT * FROM trades ORDER BY trade_time")
        trades = [dict(r) for r in cursor.fetchall()]
        pnl, win_count, loss_count = self._calculate_pnl(trades)

        # 6. 最大回撤 (基于持仓市值)
        cursor.execute("SELECT * FROM account_snapshots ORDER BY timestamp")
        snapshots = [dict(r) for r in cursor.fetchall()]
        max_dd = self._calculate_max_drawdown(snapshots)

        return {
            "total_signals": total_signals,
            "buy_signals": buy_signals,
            "sell_signals": sell_signals,
            "total_trades": total_trades,
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_shares": total_shares,
            "avg_trade_price": round(avg_trade_price, 2),
            "open_positions": len(positions),
            "positions": positions,
            "risk_rejects": risk_rejects,
            "pnl": round(pnl, 2),
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate": round(win_count / (win_count + loss_count) * 100, 1) if (win_count + loss_count) > 0 else 0,
            "max_drawdown": round(max_dd, 2),
        }

    def _calculate_pnl(self, trades: List[Dict[str, Any]]) -> tuple:
        """简化 FIFO PnL 计算。"""
        pnl = 0.0
        win_count = 0
        loss_count = 0
        # symbol -> list of (price, qty) 持仓队列
        holdings: Dict[str, List[tuple]] = {}

        for t in trades:
            sym = t["symbol"]
            qty = t["quantity"]
            price = t["price"]
            direction = t["direction"]

            if direction == "BUY":
                holdings.setdefault(sym, []).append((price, qty))
            else:  # SELL
                remaining = qty
                while remaining > 0 and holdings.get(sym):
                    buy_price, buy_qty = holdings[sym][0]
                    closed = min(remaining, buy_qty)
                    trade_pnl = (price - buy_price) * closed
                    pnl += trade_pnl
                    if trade_pnl > 0:
                        win_count += 1
                    elif trade_pnl < 0:
                        loss_count += 1
                    remaining -= closed
                    if closed >= buy_qty:
                        holdings[sym].pop(0)
                    else:
                        holdings[sym][0] = (buy_price, buy_qty - closed)

        return pnl, win_count, loss_count

    def _calculate_max_drawdown(self, snapshots: List[Dict[str, Any]]) -> float:
        """基于账户余额计算最大回撤。MVP 中没有 account_snapshots 写入，回退到 0。"""
        if not snapshots:
            return 0.0
        values = [s.get("balance", 0) for s in snapshots]
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd * 100  # 百分比

    def print_report(self, symbol: str, bars_count: int):
        stats = self.analyze()
        print("\n" + "=" * 60)
        print(f" 回测报告: {symbol}")
        print(f" K线数量: {bars_count}")
        print("=" * 60)
        print(f" 信号总数:        {stats['total_signals']}")
        print(f"   - BUY 信号:    {stats['buy_signals']}")
        print(f"   - SELL 信号:   {stats['sell_signals']}")
        print(f" 成交总数:        {stats['total_trades']}")
        print(f"   - BUY 成交:    {stats['buy_trades']}")
        print(f"   - SELL 成交:   {stats['sell_trades']}")
        print(f" 总成交股数:      {stats['total_shares']}")
        print(f" 平均成交价:      ${stats['avg_trade_price']}")
        print(f"\n 盈亏 (PnL):      ${stats['pnl']}")
        print(f" 盈利次数:        {stats['win_count']}")
        print(f" 亏损次数:        {stats['loss_count']}")
        print(f" 胜率:            {stats['win_rate']}%")
        print(f"\n 剩余持仓数:      {stats['open_positions']}")
        print(f" 风控拒单次数:    {stats['risk_rejects']}")
        if stats['positions']:
            print("\n 剩余持仓明细:")
            for p in stats['positions']:
                print(f"   {p['symbol']:12s} {p['direction']:6s} {p['volume']:4d}股 @ ${p['price']:.2f}")
        print("=" * 60)


def run_backtest(
    symbol: str,
    interval: str,
    period: str,
    strategy_cls: Type[BaseStrategy],
    strategy_config: Dict[str, Any],
    skip_risk: bool = False,
) -> int:
    """
    对单个标的运行回测。
    返回处理的 bar 数量。
    """
    logger.info(f"[Backtest] 开始回测: {symbol} strategy={strategy_cls.__name__} interval={interval} period={period}")

    # 1. 下载历史数据
    bars = fetch_bars(symbol, interval=interval, period=period)
    if not bars:
        logger.error(f"[Backtest] 无法获取数据，跳过: {symbol}")
        return 0

    # 2. 准备独立回测数据库
    db_path = PROJECT_ROOT / "data" / f"backtest_{symbol.replace('.', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    db = Database(db_path)
    db.init_schema()

    # 3. 初始化风控与策略
    risk = RiskEngine(db)
    cfg = dict(strategy_config)
    cfg["symbols"] = [symbol]
    if skip_risk:
        cfg["check_risk_before_order"] = False
        logger.info("[Backtest] 已跳过风控限制，展示原始信号")
    else:
        logger.info("[Backtest] 启用风控限制")

    strategy = strategy_cls(cfg, risk, db)

    # 4. 逐条回放
    for bar in bars:
        risk.update_market_price(symbol, bar["close"])
        strategy.on_bar(bar)

    # 5. 输出报告
    analyzer = PerformanceAnalyzer(db)
    analyzer.print_report(symbol, len(bars))

    db.close()
    return len(bars)


def setup_logging():
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"backtest_{datetime.now().strftime('%Y%m%d')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )


def main():
    parser = argparse.ArgumentParser(description="Yahoo Finance 历史数据回测")
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="回测标的，例如 US.AAPL US.TSLA。默认使用 strategy.yaml 配置")
    parser.add_argument("--strategy", default="ma", choices=["ma", "rsi"],
                        help="策略类型: ma (双均线) 或 rsi (默认 ma)")
    parser.add_argument("--interval", default="1h",
                        help="K线周期: 1m, 5m, 15m, 1h, 1d (默认 1h)")
    parser.add_argument("--period", default="1mo",
                        help="数据区间: 1d, 5d, 1mo, 3mo (默认 1mo)")
    parser.add_argument("--skip-risk", action="store_true",
                        help="跳过风控限制，展示策略原始信号")
    args = parser.parse_args()

    setup_logging()

    # 读取配置
    config = get_app_config()
    strategy_cfg = config.strategy.get(args.strategy, {})

    symbols = args.symbols or strategy_cfg.get("symbols", ["US.AAPL"])
    strategy_cls = STRATEGY_REGISTRY[args.strategy]

    for sym in symbols:
        run_backtest(
            symbol=sym,
            interval=args.interval,
            period=args.period,
            strategy_cls=strategy_cls,
            strategy_config=strategy_cfg,
            skip_risk=args.skip_risk,
        )


if __name__ == "__main__":
    main()
