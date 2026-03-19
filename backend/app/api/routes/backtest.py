from __future__ import annotations

from datetime import datetime
from typing import Literal

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.ml.registry import list_entries
from app.services.binance_market import KlineQuery, fetch_klines
from app.trading.backtest import backtest_xgb_long_only
from app.services.news_sentiment import reddit_sentiment_features

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str
    interval: Literal["1m", "5m", "15m", "1h"] = "1m"
    limit: int = Field(default=300, ge=50, le=2000)
    sentiment_mode: Literal["neutral", "reddit"] = "neutral"
    trade_fraction_cash: float = Field(default=0.5, ge=0.01, le=1.0)
    fee_bps: float = 4.0
    rules_weight: float = 0.45
    ml_weight: float = 0.55
    veto_threshold: float = -0.35


class BacktestRunResponse(BaseModel):
    symbol: str
    interval: str
    as_of: datetime
    metrics: dict
    trades: list[dict]
    model_id: str | None


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(req: BacktestRequest):
    entries = list_entries()
    active = next((e for e in entries if e.active), None) or (entries[0] if entries else None)
    if active is None:
        return BacktestRunResponse(
            symbol=req.symbol,
            interval=req.interval,
            as_of=datetime.utcnow(),
            metrics={"error": "no_model_loaded"},
            trades=[],
            model_id=None,
        )

    df = await fetch_klines(KlineQuery(symbol=req.symbol, interval=req.interval, limit=req.limit))

    sentiment_by_ts = None
    if req.sentiment_mode == "reddit":
        sent = reddit_sentiment_features(
            symbols=[req.symbol],
            start=df["ts"].min(),
            end=df["ts"].max(),
        )
        if not sent.empty:
            # Map each candle timestamp to the aggregated sentiment mean.
            sentiment_by_ts = {row["ts"]: float(row["sent_mean"]) for _, row in sent.iterrows()}

    result = backtest_xgb_long_only(
        df=df,
        model_path=active.artifact_path,
        sentiment_by_ts=sentiment_by_ts,
        symbol=req.symbol,
        interval=req.interval,
        trade_fraction_cash=req.trade_fraction_cash,
        fee_bps=req.fee_bps,
        rules_weight=req.rules_weight,
        ml_weight=req.ml_weight,
        veto_threshold=req.veto_threshold,
    )

    return BacktestRunResponse(
        symbol=result.symbol,
        interval=result.interval,
        as_of=datetime.utcnow(),
        metrics=result.metrics,
        trades=[t.__dict__ for t in result.trades],
        model_id=active.id,
    )

