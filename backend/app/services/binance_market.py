from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

import httpx
import pandas as pd


BINANCE_REST_BASE = "https://api.binance.com"
# Binance /api/v3/klines allows max 1000 candles per request.
_BINANCE_KLINE_MAX = 1000
# Safety cap: ~150k candles per symbol (~105s at 1m if 50ms between pages).
_MAX_PAGINATED_PAGES = 160


def _klines_json_to_df(rows: list) -> pd.DataFrame:
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
    return df.dropna().reset_index(drop=True)


async def _http_get_klines(
    client: httpx.AsyncClient,
    *,
    symbol: str,
    interval: str,
    limit: int,
    end_time_ms: int | None,
) -> list:
    url = f"{BINANCE_REST_BASE}/api/v3/klines"
    params: dict[str, str | int] = {
        "symbol": symbol,
        "interval": interval,
        "limit": min(int(limit), _BINANCE_KLINE_MAX),
    }
    if end_time_ms is not None:
        params["endTime"] = int(end_time_ms)
    r = await client.get(url, params=params)
    r.raise_for_status()
    return r.json()


@dataclass(frozen=True)
class KlineQuery:
    symbol: str
    interval: Literal["1m", "5m", "15m", "1h"] = "1m"
    limit: int = 1000


async def fetch_klines(query: KlineQuery) -> pd.DataFrame:
    """
    Fetch OHLCV klines from Binance (spot) and return a DataFrame.
    Columns: ts, open, high, low, close, volume

    If limit > 1000, requests are paginated backwards in time (Binance max 1000 per call).
    """
    if query.limit <= _BINANCE_KLINE_MAX:
        return await _fetch_klines_single(query.symbol, query.interval, query.limit, end_time_ms=None)
    return await fetch_klines_paginated(query.symbol, query.interval, query.limit)


async def _fetch_klines_single(
    symbol: str,
    interval: str,
    limit: int,
    *,
    end_time_ms: int | None,
) -> pd.DataFrame:
    timeout = httpx.Timeout(connect=15.0, read=40.0, write=15.0, pool=15.0)
    last_exc: Exception | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(3):
            try:
                rows = await _http_get_klines(
                    client,
                    symbol=symbol,
                    interval=interval,
                    limit=limit,
                    end_time_ms=end_time_ms,
                )
                if not rows:
                    return pd.DataFrame()
                return _klines_json_to_df(rows)
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(0.8 * (attempt + 1))
                    continue
                raise RuntimeError(
                    f"Failed to fetch Binance klines for {symbol} after retries: {type(exc).__name__}"
                ) from exc
    raise RuntimeError(f"Failed to fetch Binance klines for {symbol}: {last_exc}")


async def fetch_klines_paginated(symbol: str, interval: str, total_limit: int) -> pd.DataFrame:
    """
    Fetch up to `total_limit` most recent candles by paging with endTime.
    """
    if total_limit <= 0:
        return pd.DataFrame()
    chunks: list[pd.DataFrame] = []
    remaining = int(total_limit)
    end_time_ms: int | None = None
    pages = 0
    timeout = httpx.Timeout(connect=15.0, read=40.0, write=15.0, pool=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        while remaining > 0 and pages < _MAX_PAGINATED_PAGES:
            batch = min(_BINANCE_KLINE_MAX, remaining)
            rows = None
            for attempt in range(3):
                try:
                    rows = await _http_get_klines(
                        client,
                        symbol=symbol,
                        interval=interval,
                        limit=batch,
                        end_time_ms=end_time_ms,
                    )
                    break
                except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
                    if attempt < 2:
                        await asyncio.sleep(0.8 * (attempt + 1))
                        continue
                    raise RuntimeError(
                        f"Failed to fetch Binance klines page for {symbol}: {type(exc).__name__}"
                    ) from exc
            if not rows:
                break
            df = _klines_json_to_df(rows)
            if df.empty:
                break
            chunks.append(df)
            pages += 1
            remaining -= len(df)
            # Next page ends before the oldest candle in this batch (rows are ascending by open time).
            oldest_open = int(df["ts"].iloc[0].timestamp() * 1000)
            end_time_ms = oldest_open - 1
            if len(df) < batch:
                break
            await asyncio.sleep(0.05)
    if not chunks:
        return pd.DataFrame()
    out = pd.concat(chunks, ignore_index=True)
    out = out.sort_values("ts").drop_duplicates(subset=["ts"], keep="first").reset_index(drop=True)
    if len(out) > total_limit:
        out = out.tail(total_limit).reset_index(drop=True)
    return out

