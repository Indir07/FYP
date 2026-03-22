from __future__ import annotations

from datetime import datetime
from typing import Literal

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.ml.registry import get_model_for_symbol
from app.services.binance_market import KlineQuery, fetch_klines
from app.trading.backtest import backtest_xgb_long_only
from app.services.news_sentiment import reddit_sentiment_features

router = APIRouter()


class BacktestRequest(BaseModel):
    symbol: str
    interval: Literal["1m", "5m", "15m", "1h"] = "1m"
    # Binance klines are paginated server-side (see fetch_klines); large limits OK.
    limit: int = Field(default=10080, ge=50, le=50_000)
    sentiment_mode: Literal["neutral", "reddit"] = "neutral"
    trade_fraction_cash: float = Field(default=0.5, ge=0.01, le=1.0)
    fee_bps: float = 4.0
    rules_weight: float = 0.45
    ml_weight: float = 0.55
    veto_threshold: float = -0.35
    # If true, BUY/SELL decisions use model probability thresholds directly:
    # - BUY when proba_up >= buy_proba_threshold
    # - SELL when proba_up <= sell_proba_threshold
    use_proba_thresholds: bool = False
    buy_proba_threshold: float = 0.55
    sell_proba_threshold: float = 0.45
    # Fused score thresholds:
    # - BUY when fused > buy_fused_threshold
    # - SELL when fused < sell_fused_threshold
    buy_fused_threshold: float = 0.15
    sell_fused_threshold: float = -0.15
    # Risk management (aim: reduce maximum loss / max drawdown).
    # Values are in basis points (bps). Set to 0 to disable.
    stop_loss_bps: float = Field(default=250.0, ge=0.0, le=50_000.0)
    take_profit_bps: float = Field(default=400.0, ge=0.0, le=50_000.0)
    trailing_stop_bps: float = Field(default=0.0, ge=0.0, le=50_000.0)
    max_drawdown_limit: float = Field(default=0.05, ge=0.0, le=1.0)


class BacktestRunResponse(BaseModel):
    symbol: str
    interval: str
    as_of: datetime
    metrics: dict
    trades: list[dict]
    model_id: str | None


@router.post("/run", response_model=BacktestRunResponse)
async def run_backtest(req: BacktestRequest):
    model_entry = get_model_for_symbol(req.symbol)
    if model_entry is None:
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
        model_path=model_entry.artifact_path,
        sentiment_by_ts=sentiment_by_ts,
        symbol=req.symbol,
        interval=req.interval,
        trade_fraction_cash=req.trade_fraction_cash,
        fee_bps=req.fee_bps,
        rules_weight=req.rules_weight,
        ml_weight=req.ml_weight,
        veto_threshold=req.veto_threshold,
        buy_fused_threshold=req.buy_fused_threshold,
        sell_fused_threshold=req.sell_fused_threshold,
        use_proba_thresholds=req.use_proba_thresholds,
        buy_proba_threshold=req.buy_proba_threshold,
        sell_proba_threshold=req.sell_proba_threshold,
        stop_loss_bps=req.stop_loss_bps,
        take_profit_bps=req.take_profit_bps,
        trailing_stop_bps=req.trailing_stop_bps,
        max_drawdown_limit=req.max_drawdown_limit,
    )

    return BacktestRunResponse(
        symbol=result.symbol,
        interval=result.interval,
        as_of=datetime.utcnow(),
        metrics=result.metrics,
        trades=[t.__dict__ for t in result.trades],
        model_id=model_entry.id,
    )

