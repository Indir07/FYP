from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.binance_coins import get_recommended_universe
from app.services.binance_coins import CoinCandidate

router = APIRouter()


class UniverseResponse(BaseModel):
    as_of: datetime
    quote_asset: str
    criteria: dict
    coins: list[CoinCandidate]


@router.get("/recommended", response_model=UniverseResponse)
async def recommended_coins(
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
    coins = await get_recommended_universe(
        quote_asset=quote_asset,
        limit=limit,
        max_price=max_price,
        min_change_24h=min_change_24h,
        min_quote_volume_24h=min_quote_volume_24h,
    )
    return UniverseResponse(
        as_of=datetime.utcnow(),
        quote_asset=quote_asset,
        criteria={
            "max_price": max_price,
            "min_change_24h": min_change_24h,
            "min_quote_volume_24h": min_quote_volume_24h,
        },
        coins=coins,
    )

