from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.services.binance_market import KlineQuery, fetch_klines

router = APIRouter()


class LatestPriceResponse(BaseModel):
    symbol: str
    as_of: datetime
    price: float


class KlinesResponse(BaseModel):
    symbol: str
    interval: str
    rows: list[dict]


@router.get("/klines", response_model=KlinesResponse)
async def klines(
    symbol: str,
    interval: Literal["1m", "5m", "15m", "1h"] = "1m",
    limit: int = Query(500, ge=50, le=1000),
):
    df = await fetch_klines(KlineQuery(symbol=symbol, interval=interval, limit=limit))
    rows = df.to_dict(orient="records")
    return KlinesResponse(symbol=symbol, interval=interval, rows=rows)


@router.get("/latest", response_model=LatestPriceResponse)
async def latest(symbol: str):
    df = await fetch_klines(KlineQuery(symbol=symbol, interval="1m", limit=2))
    if df.empty:
        return LatestPriceResponse(symbol=symbol, as_of=datetime.utcnow(), price=float("nan"))
    price = float(df["close"].iloc[-1])
    return LatestPriceResponse(symbol=symbol, as_of=datetime.utcnow(), price=price)

