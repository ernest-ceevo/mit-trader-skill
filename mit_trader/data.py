"""Daily data: Alpaca (env keys) or yfinance for stocks/ETFs, ccxt public OHLCV for crypto."""
import os
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from .common import is_crypto


def _cache_path(cfg, symbol):
    return cfg["_home"] / "cache" / (symbol.replace("/", "-") + ".csv")


def _fetch_alpaca(symbol, years):
    """Daily OHLCV from Alpaca Data API. Keys come from ALPACA_API_KEY / ALPACA_SECRET_KEY env vars."""
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame

    key = os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise RuntimeError("未设置 ALPACA_API_KEY / ALPACA_SECRET_KEY 环境变量")
    client = StockHistoricalDataClient(key, secret)
    start = datetime.now(timezone.utc) - timedelta(days=365 * years + 7)
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        limit=10000,
        feed="sip",  # 付费订阅是 sip；免费会退回 iex
    )
    bars = client.get_stock_bars(req)
    df = bars.df if hasattr(bars, "df") else bars
    if df is None or (hasattr(df, "empty") and df.empty):
        raise RuntimeError(f"Alpaca 没有返回 {symbol} 的数据")
    if isinstance(df.index, pd.MultiIndex):
        if symbol not in df.index.get_level_values(0):
            raise RuntimeError(f"Alpaca 没有返回 {symbol} 的数据")
        df = df.xs(symbol, level=0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    # 去掉还没收盘的当天 K 线
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    return df[df.index < today]


def _fetch_yf(symbol, years):
    import yfinance as yf
    df = yf.download(symbol, period=f"{years}y", interval="1d", auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError(f"yfinance 没有返回 {symbol} 的数据")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


def _fetch_ccxt(symbol, years, exchange):
    import ccxt
    ex = getattr(ccxt, exchange)({"enableRateLimit": True})
    since = int((datetime.now(timezone.utc) - timedelta(days=365 * years)).timestamp() * 1000)
    rows = []
    while True:
        batch = ex.fetch_ohlcv(symbol, "1d", since=since, limit=300)
        if not batch:
            if not rows and since < time.time() * 1000 - 400 * 86_400_000:
                since += 180 * 86_400_000  # 交易所历史没那么长：往后挪再试
                continue
            break
        rows.extend(batch)
        nxt = batch[-1][0] + 86_400_000
        if nxt <= since or len(batch) < 2:
            break
        since = nxt
        if since > time.time() * 1000:
            break
    if not rows:
        raise RuntimeError(f"{exchange} 没有返回 {symbol} 的数据")
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).drop_duplicates("ts")
    df.index = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
    df = df.drop(columns="ts")
    # 去掉还没收盘的当天 K 线
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    return df[df.index < today]


def get_prices(cfg, symbol, refresh_hours=12):
    """Return daily OHLCV DataFrame. Uses a local CSV cache; refetches when older than refresh_hours."""
    path = _cache_path(cfg, symbol)
    if path.exists() and (time.time() - path.stat().st_mtime) < refresh_hours * 3600:
        return pd.read_csv(path, index_col=0, parse_dates=True)
    years = cfg["data"]["years"]
    source = cfg["data"].get("source")
    try:
        if is_crypto(symbol):
            df = _fetch_ccxt(symbol, years, cfg["data"]["crypto_exchange"])
        elif source == "alpaca":
            try:
                df = _fetch_alpaca(symbol, years)
            except Exception:  # Alpaca 失败退回 yfinance
                df = _fetch_yf(symbol, years)
        else:
            df = _fetch_yf(symbol, years)
        df = df.dropna()
        df.to_csv(path)
        return df
    except Exception:
        if path.exists():  # 网络失败就退回旧缓存
            return pd.read_csv(path, index_col=0, parse_dates=True)
        raise


def synthetic_prices(seed=0, n=2520, drift=0.0003, vol=0.012, planted_momentum=0.0):
    """Synthetic random-walk prices for smoke tests. planted_momentum>0 adds a real autocorrelation edge."""
    rng = np.random.default_rng(seed)
    eps = rng.standard_normal(n) * vol
    r = np.zeros(n)
    trend = 0.0
    for t in range(n):
        trend = 0.97 * trend + eps[t]
        r[t] = drift + eps[t] + planted_momentum * trend
    idx = pd.bdate_range(end=pd.Timestamp("2026-11-20"), periods=n)
    close = 100 * np.exp(np.cumsum(r))
    df = pd.DataFrame({"open": close, "high": close * 1.005, "low": close * 0.995, "close": close, "volume": 1e6}, index=idx)
    return df
