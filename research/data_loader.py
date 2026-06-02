"""
research/data_loader.py — 美股数据加载 + 特征工程
====================================================
数据源: Yahoo Finance (yfinance)
特征: MA, RSI, MACD, volatility, volume
缓存: CSV 避免重复下载
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def _add_price_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    h = df["high"]
    l = df["low"]
    v = df["volume"]

    # Moving averages
    df["ma5"] = c.rolling(5, min_periods=1).mean()
    df["ma20"] = c.rolling(20, min_periods=1).mean()
    df["ma50"] = c.rolling(50, min_periods=1).mean()
    df["ma200"] = c.rolling(200, min_periods=1).mean()

    # Price relative to MAs
    df["price_vs_ma20"] = (c - df["ma20"]) / df["ma20"]
    df["price_vs_ma50"] = (c - df["ma50"]) / df["ma50"]
    df["price_vs_ma200"] = (c - df["ma200"]) / df["ma200"]

    # RSI(14)
    delta = c.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    df["rsi"] = 100.0 - (100.0 / (1.0 + rs))

    # MACD
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["macd"] = ema12 - ema26
    df["macd_signal"] = df["macd"].ewm(span=9, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    # ATR(14)
    tr = pd.concat([
        (h - l).abs(),
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    df["atr"] = tr.ewm(alpha=1/14, adjust=False).mean()

    # Volume
    df["volume_ma20"] = v.rolling(20, min_periods=1).mean()
    df["volume_ratio"] = v / df["volume_ma20"]

    # Returns + volatility
    df["daily_ret"] = c.pct_change()
    df["rvol7d"] = (df["daily_ret"].rolling(7, min_periods=4).std() * math.sqrt(252) * 100)
    df["rvol30d"] = (df["daily_ret"].rolling(30, min_periods=10).std() * math.sqrt(252) * 100)

    return df


def load_data(
    symbol: str = "AAPL",
    interval: str = "1d",
    period: str = "5y",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Load single stock data with feature engineering. Cached to CSV."""
    cache_file = DATA_DIR / f"{symbol}_{interval}_{period}.csv"
    if not force_refresh and cache_file.exists():
        df = pd.read_csv(cache_file, parse_dates=["date"])
        df = _add_price_features(df)
        print(f"[data] Loaded {symbol} ({len(df)} rows from cache)")
        return df.sort_values("date").reset_index(drop=True)

    ticker = yf.Ticker(symbol)
    df = ticker.history(period=period, interval=interval)
    if df.empty:
        raise ValueError(f"No data for {symbol} interval={interval} period={period}")
    df = df.reset_index()
    df = df.rename(columns={
        "Date": "date", "Open": "open", "High": "high",
        "Low": "low", "Close": "close", "Volume": "volume",
    })
    # Handle MultiIndex columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() if c[0] != "Date" else "date" for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    df["date"] = pd.to_datetime(df["date"])
    df = _add_price_features(df)
    df.to_csv(cache_file, index=False)
    print(f"[data] Downloaded + cached {symbol} ({len(df)} rows)")
    return df.sort_values("date").reset_index(drop=True)


def load_multi_assets(
    symbols: list[str],
    interval: str = "1d",
    period: str = "5y",
) -> dict[str, pd.DataFrame]:
    """Load multiple stocks in parallel. Returns {symbol: dataframe}."""
    return {s: load_data(s, interval, period) for s in symbols}


if __name__ == "__main__":
    df = load_data("AAPL")
    print(f"Columns: {list(df.columns)}")
    print(df[["date", "close", "ma20", "rsi", "macd"]].tail(5))
