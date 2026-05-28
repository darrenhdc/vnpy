# =============================================================================
# Yahoo Finance 历史数据获取模块
# =============================================================================
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

# Yahoo ticker 映射: 我们的内部格式 -> Yahoo 格式
SYMBOL_MAP = {
    "US.AAPL": "AAPL",
    "US.TSLA": "TSLA",
    "US.SPY": "SPY",
    "US.MSFT": "MSFT",
    "US.AMZN": "AMZN",
    "US.GOOG": "GOOG",
    "US.NVDA": "NVDA",
    "US.META": "META",
}


def to_yahoo_ticker(symbol: str) -> str:
    """将内部标的格式转换为 Yahoo Finance ticker。"""
    if symbol in SYMBOL_MAP:
        return SYMBOL_MAP[symbol]
    # 简单规则: US.XXX -> XXX
    if symbol.startswith("US."):
        return symbol.split(".", 1)[1]
    return symbol


def fetch_bars(
    symbol: str,
    interval: str = "1m",
    period: str = "5d",
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    从 Yahoo Finance 下载历史 K 线。

    Parameters
    ----------
    symbol : str
        内部标的代码，如 US.AAPL
    interval : str
        Yahoo 支持: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
        注意: 1m 数据最多提供最近 7 天
    period : str
        数据区间: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    start / end : str, optional
        格式 YYYY-MM-DD，如果提供则覆盖 period

    Returns
    -------
    List[Dict]
        标准 bar dict 列表，可直接喂给策略 on_bar()
    """
    yahoo_ticker = to_yahoo_ticker(symbol)
    logger.info(f"[YahooFeeder] 开始下载 {symbol} (Yahoo: {yahoo_ticker})  interval={interval} period={period}")

    try:
        df = yf.download(
            yahoo_ticker,
            period=period if start is None else None,
            start=start,
            end=end,
            interval=interval,
            progress=False,
            auto_adjust=True,   # 复权价格
        )
    except Exception as e:
        logger.error(f"[YahooFeeder] 下载失败: {e}")
        return []

    if df is None or df.empty:
        logger.warning(f"[YahooFeeder] 未获取到数据: {symbol}")
        return []

    # yfinance 返回的列可能是 MultiIndex (Ticker, Price)
    # 扁平化处理
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    # 确保列名小写
    df.columns = [str(c).lower().replace("adj close", "close") for c in df.columns]

    bars = []
    for dt, row in df.iterrows():
        bar = {
            "symbol": symbol,
            "interval": interval,
            "timestamp": pd.Timestamp(dt).isoformat(),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "volume": int(row.get("volume", 0)),
        }
        bars.append(bar)

    logger.info(f"[YahooFeeder] 下载完成: {symbol} 共 {len(bars)} 条 bar")
    return bars
