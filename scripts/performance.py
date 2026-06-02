#!/usr/bin/env python3
# =============================================================================
# CLI: performance —— 查询回测/实盘绩效
# =============================================================================
"""
使用示例:
    ./scripts/performance.py --backtest-db data/backtest_US_AAPL_*.db
    ./scripts/performance.py --live-db data/trading.db
    ./scripts/performance.py --symbol US.AAPL --days 30
"""
import sys
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime, timedelta

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def analyze_backtest_db(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 信号统计
    cur.execute("SELECT COUNT(*) FROM strategy_signals")
    total_signals = cur.fetchone()[0]

    # 成交统计
    cur.execute("SELECT COUNT(*), SUM(quantity), AVG(price) FROM trades")
    row = cur.fetchone()
    total_trades, total_shares, avg_price = row[0], row[1] or 0, row[2] or 0

    # 风控
    cur.execute("SELECT COUNT(*) FROM risk_events WHERE event_type='ORDER_REJECTED'")
    rejects = cur.fetchone()[0]

    # 盈亏 (FIFO 简化)
    cur.execute("SELECT * FROM trades ORDER BY trade_time")
    trades = [dict(r) for r in cur.fetchall()]
    pnl = 0.0
    holdings = []
    for t in trades:
        if t["direction"] == "BUY":
            holdings.append((t["price"], t["quantity"]))
        else:
            qty = t["quantity"]
            while qty > 0 and holdings:
                buy_p, buy_q = holdings[0]
                closed = min(qty, buy_q)
                pnl += (t["price"] - buy_p) * closed
                qty -= closed
                if closed >= buy_q:
                    holdings.pop(0)
                else:
                    holdings[0] = (buy_p, buy_q - closed)

    conn.close()

    print(f"\n=== 绩效报告: {db_path.name} ===")
    print(f"  信号总数:      {total_signals}")
    print(f"  成交总数:      {total_trades}")
    print(f"  总成交股数:    {total_shares}")
    print(f"  平均成交价:    ${avg_price:.2f}" if avg_price else "  平均成交价:    N/A")
    print(f"  估算盈亏:      ${pnl:.2f}")
    print(f"  风控拒单:      {rejects}")
    print("=" * 40)


def analyze_live_db(db_path: Path, symbol: str = None, days: int = 30):
    if not db_path.exists():
        print(f"[Error] 数据库不存在: {db_path}")
        return
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # 最近交易
    sql = "SELECT * FROM trades WHERE trade_time > ?"
    params = (since,)
    if symbol:
        sql += " AND symbol=?"
        params += (symbol,)
    cur.execute(sql, params)
    trades = [dict(r) for r in cur.fetchall()]

    print(f"\n=== 实盘绩效 ({days}天) ===")
    print(f"  数据库: {db_path}")
    if symbol:
        print(f"  标的:   {symbol}")
    print(f"  成交笔数: {len(trades)}")

    if trades:
        buy_val = sum(t["price"] * t["quantity"] for t in trades if t["direction"] == "BUY")
        sell_val = sum(t["price"] * t["quantity"] for t in trades if t["direction"] == "SELL")
        print(f"  买入金额: ${buy_val:,.2f}")
        print(f"  卖出金额: ${sell_val:,.2f}")

    conn.close()
    print("=" * 40)


def main():
    parser = argparse.ArgumentParser(description="绩效查询工具")
    parser.add_argument("--backtest-db", type=Path, help="回测数据库路径")
    parser.add_argument("--live-db", type=Path, default=PROJECT_ROOT / "data" / "trading.db",
                        help="实盘数据库路径")
    parser.add_argument("--symbol", help="筛选标的")
    parser.add_argument("--days", type=int, default=30, help="最近 N 天")
    args = parser.parse_args()

    if args.backtest_db:
        analyze_backtest_db(args.backtest_db)
    else:
        analyze_live_db(args.live_db, args.symbol, args.days)


if __name__ == "__main__":
    main()
