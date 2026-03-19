from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx
import pandas as pd


BINANCE_REST_BASE = "https://api.binance.com"


@dataclass(frozen=True)
class KlineQuery:
    symbol: str
    interval: Literal["1m", "5m", "15m", "1h"] = "1m"
    limit: int = 1000


async def fetch_klines(query: KlineQuery) -> pd.DataFrame:
    """
    Fetch OHLCV klines from Binance (spot) and return a DataFrame.
    Columns: ts, open, high, low, close, volume
    """
    url = f"{BINANCE_REST_BASE}/api/v3/klines"
    params = {"symbol": query.symbol, "interval": query.interval, "limit": query.limit}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        rows = r.json()

    # Binance format:
    # [ openTime, open, high, low, close, volume, closeTime, quoteAssetVol, trades, ...]
    df = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "num_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    df = df[["open_time", "open", "high", "low", "close", "volume"]].copy()
    df.rename(columns={"open_time": "ts"}, inplace=True)
    df["ts"] = pd.to_datetime(df["ts"], unit="ms", utc=True)
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna().reset_index(drop=True)
    return df

