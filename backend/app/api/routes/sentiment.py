from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

import pandas as pd

from app.services.news_sentiment import reddit_sentiment_features

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
        sent = reddit_sentiment_features(symbols=[req.symbol], start=start, end=pd.Timestamp(now))
        if not sent.empty and float(sent["sent_count"].max()) > 0:
            avg = float(sent["sent_mean"].mean())
            count = int(sent["sent_count"].sum())

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

