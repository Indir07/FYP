from __future__ import annotations

import asyncio
import math
from typing import Literal, TypedDict

import httpx

from pydantic import BaseModel


class _Binance24hTicker(TypedDict, total=False):
    symbol: str
    lastPrice: str
    priceChangePercent: str
    quoteVolume: str


BINANCE_REST_BASE = "https://api.binance.com"


class CoinCandidate(BaseModel):
    symbol: str
    last_price: float
    price_change_percent_24h: float
    quote_volume_24h: float
    score: float


def _to_float(x: str | None) -> float | None:
    if x is None:
        return None
    try:
        return float(x)
    except ValueError:
        return None


def _score(last_price: float, change_pct: float, quote_vol: float) -> float:
    # Higher change + higher liquidity + lower price.
    # Keep it stable: log for volume, mild penalty for higher price within "cheap".
    vol_term = math.log10(max(1.0, quote_vol))
    price_penalty = math.log10(max(1e-6, last_price))  # 0.. for <1, >0 for >1
    return (change_pct * 1.0) + (vol_term * 2.0) - (price_penalty * 1.5)


async def get_recommended_universe(
    *,
    quote_asset: Literal["USDT"] = "USDT",
    limit: int = 20,
    max_price: float = 2.0,
    min_change_24h: float = 3.0,
    min_quote_volume_24h: float = 5_000_000.0,
) -> list[CoinCandidate]:
    url = f"{BINANCE_REST_BASE}/api/v3/ticker/24hr"
    timeout = httpx.Timeout(connect=12.0, read=30.0, write=12.0, pool=12.0)
    data: list[_Binance24hTicker] | None = None
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(3):
            try:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
                break
            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.ConnectError, httpx.RemoteProtocolError):
                if attempt < 2:
                    await asyncio.sleep(0.7 * (attempt + 1))
                    continue
                raise

    candidates: list[CoinCandidate] = []
    suffix = quote_asset.upper()

    for t in (data or []):
        symbol = t.get("symbol")
        if not symbol or not symbol.endswith(suffix):
            continue
        if symbol.endswith("UPUSDT") or symbol.endswith("DOWNUSDT"):
            continue

        last_price = _to_float(t.get("lastPrice"))
        change_pct = _to_float(t.get("priceChangePercent"))
        quote_vol = _to_float(t.get("quoteVolume"))
        if last_price is None or change_pct is None or quote_vol is None:
            continue

        if last_price > max_price:
            continue
        if change_pct < min_change_24h:
            continue
        if quote_vol < min_quote_volume_24h:
            continue

        candidates.append(
            CoinCandidate(
                symbol=symbol,
                last_price=last_price,
                price_change_percent_24h=change_pct,
                quote_volume_24h=quote_vol,
                score=_score(last_price, change_pct, quote_vol),
            )
        )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:limit]

