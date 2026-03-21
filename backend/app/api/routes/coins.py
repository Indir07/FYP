from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.binance_coins import get_recommended_universe
from app.services.binance_coins import CoinCandidate
from app.services.binance_coins import get_top10_famous_growing_universe

router = APIRouter()

_FALLBACK_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT"]
_FALLBACK_TOP10 = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT", "TRXUSDT", "AVAXUSDT", "LINKUSDT"]


class UniverseResponse(BaseModel):
    as_of: datetime
    quote_asset: str
    criteria: dict
    coins: list[CoinCandidate]


@router.get("/recommended", response_model=UniverseResponse)
async def recommended_coins(
    strategy: Literal["cheap_growing", "top10_famous_growing"] = "cheap_growing",
    quote_asset: Literal["USDT"] = "USDT",
    limit: int = Query(20, ge=5, le=100),
    max_price: float = Query(2.0, gt=0),
    min_change_24h: float = Query(3.0),
    min_quote_volume_24h: float = Query(5_000_000.0, gt=0),
):
    """
    "Cheapest + growing" coin universe:
    - cheap: last_price <= max_price
    - growing: priceChangePercent >= min_change_24h
    - liquid: quoteVolume >= min_quote_volume_24h
    Sorted by a simple score combining growth + liquidity and penalizing higher price.
    """
    try:
        if strategy == "top10_famous_growing":
            coins = await get_top10_famous_growing_universe(limit=min(limit, 10))
        else:
            coins = await get_recommended_universe(
                quote_asset=quote_asset,
                limit=limit,
                max_price=max_price,
                min_change_24h=min_change_24h,
                min_quote_volume_24h=min_quote_volume_24h,
            )
    except Exception:
        # Graceful fallback so the UI can still load and fetch market data.
        fallback = _FALLBACK_TOP10 if strategy == "top10_famous_growing" else _FALLBACK_SYMBOLS
        coins = [
            CoinCandidate(
                symbol=s,
                last_price=0.0,
                price_change_percent_24h=0.0,
                quote_volume_24h=0.0,
                score=0.0,
            )
            for s in fallback[:limit]
        ]
    return UniverseResponse(
        as_of=datetime.utcnow(),
        quote_asset=quote_asset,
        criteria={
            "strategy": strategy,
            "max_price": max_price,
            "min_change_24h": min_change_24h,
            "min_quote_volume_24h": min_quote_volume_24h,
        },
        coins=coins,
    )

