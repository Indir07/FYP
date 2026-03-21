from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import pandas as pd
import numpy as np

from app.services.news_sentiment import reddit_sentiment_features
from app.services.binance_market import KlineQuery, fetch_klines

router = APIRouter()
_analyzer = SentimentIntensityAnalyzer()


class SentimentScoreRequest(BaseModel):
    symbol: str | None = None
    texts: list[str] = Field(default_factory=list, min_length=1)


class SentimentScoreResponse(BaseModel):
    as_of: datetime
    symbol: str | None
    count: int
    compound_avg: float
    label: str


@router.post("/score", response_model=SentimentScoreResponse)
async def score(req: SentimentScoreRequest):
    # If symbol is provided, try to compute sentiment from Reddit posts first.
    # If Reddit creds are missing or no posts were found, fall back to VADER on provided texts.
    avg: float | None = None
    label: str | None = None
    count: int = 0

    if req.symbol:
        now = datetime.now(timezone.utc)
        start = pd.Timestamp(now) - pd.Timedelta(minutes=60)
        try:
            sent = await asyncio.wait_for(
                asyncio.to_thread(
                    reddit_sentiment_features,
                    symbols=[req.symbol],
                    start=start,
                    end=pd.Timestamp(now),
                    post_limit=40,
                ),
                timeout=2.5,
            )
            if not sent.empty and float(sent["sent_count"].max()) > 0:
                avg = float(sent["sent_mean"].mean())
                count = int(sent["sent_count"].sum())
        except Exception:
            # Timeout/network issues should not stall dashboard sentiment.
            avg = None

    # If Reddit has no usable coverage, derive a symbol-specific proxy from
    # short-term market behavior so dashboard sentiment is dynamic per coin.
    if avg is None and req.symbol:
        try:
            kl = await fetch_klines(KlineQuery(symbol=req.symbol, interval="1m", limit=120))
            if len(kl) >= 30:
                close = kl["close"].astype(float).to_numpy()
                ret_1 = (close[-1] / close[-2] - 1.0) if close[-2] != 0 else 0.0
                ret_15 = (close[-1] / close[-16] - 1.0) if close[-16] != 0 else 0.0
                vol = float(np.std(np.diff(np.log(np.maximum(close, 1e-9)))))
                # Momentum contributes positively, volatility penalizes confidence.
                proxy_raw = (ret_1 * 1200.0) + (ret_15 * 300.0) - (vol * 25.0)
                avg = float(np.tanh(proxy_raw))
                count = 1
        except Exception:
            # Keep graceful fallback behavior.
            avg = None

    if avg is None:
        scores = [_analyzer.polarity_scores(t).get("compound", 0.0) for t in req.texts]
        avg = float(sum(scores) / max(1, len(scores)))
        count = len(scores)

    if avg > 0.25:
        label = "positive"
    elif avg < -0.25:
        label = "negative"
    else:
        label = "neutral"

    return SentimentScoreResponse(
        as_of=datetime.utcnow(),
        symbol=req.symbol,
        count=count,
        compound_avg=avg,
        label=label,
    )

