from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
import joblib

from app.ml.features import build_features
from app.ml.train_xgb import FEATURE_COLS
from app.trading.decision import _rule_signal


@dataclass(frozen=True)
class BacktestTrade:
    ts: str
    symbol: str
    side: Literal["BUY", "SELL"]
    qty: float
    price: float
    fee: float
    pnl: float


@dataclass(frozen=True)
class BacktestResult:
    symbol: str
    interval: str
    metrics: dict[str, Any]
    trades: list[BacktestTrade]


def _equity_metrics(equity: np.ndarray, periods_per_year: float) -> dict[str, Any]:
    rets = np.diff(equity) / np.maximum(1e-12, equity[:-1])
    if len(rets) < 2:
        return {"sharpe": 0.0, "max_drawdown": 0.0, "final_return": float(equity[-1] - equity[0])}

    mean = float(np.mean(rets))
    std = float(np.std(rets))
    sharpe = 0.0 if std == 0 else (mean / std) * float(np.sqrt(periods_per_year))

    peaks = np.maximum.accumulate(equity)
    dd = (equity - peaks) / np.maximum(1e-12, peaks)
    max_dd = float(np.min(dd))

    return {
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "final_return": float(equity[-1] - equity[0]),
        "cagr_like": float((equity[-1] / equity[0]) ** (periods_per_year / max(1, len(rets))) - 1.0),
    }


def _periods_per_year(interval: str) -> float:
    if interval == "1m":
        return 365 * 24 * 60
    if interval == "5m":
        return 365 * 24 * 12
    if interval == "15m":
        return 365 * 24 * 4
    if interval == "1h":
        return 365 * 24
    return 365 * 24 * 60


def backtest_xgb_long_only(
    *,
    df: pd.DataFrame,
    model_path: str,
    sentiment_by_ts: dict[pd.Timestamp, float] | None = None,
    symbol: str,
    interval: str,
    trade_fraction_cash: float = 0.5,
    fee_bps: float = 4.0,
    rules_weight: float = 0.45,
    ml_weight: float = 0.55,
    veto_threshold: float = -0.35,
) -> BacktestResult:
    """
    Long-only backtest:
      - BUY when fused score > +0.15 and no position
      - SELL when fused score < -0.15 and position exists
      - HOLD otherwise
    """
    if df.empty:
        return BacktestResult(symbol=symbol, interval=interval, metrics={"error": "empty_df"}, trades=[])

    model = joblib.load(model_path)

    # Match model's expected feature columns (sentiment columns may not exist
    # in older training runs).
    expected_cols = getattr(model, "feature_names_in_", None)
    if expected_cols is None:
        try:
            expected_cols = model.get_booster().feature_names
        except Exception:
            expected_cols = None
    if expected_cols is None:
        expected_cols_list = FEATURE_COLS
    else:
        expected_cols_list = list(expected_cols)
        if len(expected_cols_list) == 0:
            expected_cols_list = FEATURE_COLS

    # Keep enough lookback for indicators.
    start_i = max(60, len(df) // 5)
    equity = np.zeros(len(df), dtype=float)
    cash = 10_000.0
    position_qty = 0.0
    entry_price = 0.0
    trades: list[BacktestTrade] = []

    fee_rate = fee_bps / 10_000.0

    for i in range(len(df)):
        ts = df["ts"].iloc[i]
        price = float(df["close"].iloc[i])

        # Mark-to-market equity
        equity[i] = cash + position_qty * price

        if i < start_i:
            continue

        ohlcv_slice = df.iloc[: i + 1].copy()
        feats = build_features(ohlcv_slice)
        if len(feats) == 0:
            continue

        # `build_features()` currently returns OHLCV-derived features only.
        # The trained model expects sentiment columns listed in `FEATURE_COLS`.
        # If we run with neutral sentiment (or Reddit creds are missing),
        # we inject deterministic defaults so the feature vector matches.
        sentiment_index = 0.0
        if sentiment_by_ts is not None:
            sentiment_index = float(sentiment_by_ts.get(ts, 0.0))
        if "sent_mean" not in feats.columns:
            feats["sent_mean"] = float(sentiment_index)
        if "sent_count" not in feats.columns:
            feats["sent_count"] = 1.0 if float(sentiment_index) != 0.0 else 0.0
        if "sent_pos_share" not in feats.columns:
            feats["sent_pos_share"] = 1.0 if float(sentiment_index) > 0 else 0.0
        if "sent_neg_share" not in feats.columns:
            feats["sent_neg_share"] = 1.0 if float(sentiment_index) < 0 else 0.0

        rule_score = _rule_signal(feats)
        X_last = feats[expected_cols_list].astype(np.float32).iloc[[-1]]
        proba_up = float(model.predict_proba(X_last)[0][1])
        ml_score = (proba_up - 0.5) * 2.0
        fused = (rules_weight * rule_score) + (ml_weight * ml_score)

        vetoed = sentiment_index <= veto_threshold
        action: Literal["BUY", "SELL", "HOLD"] = "HOLD"
        if vetoed:
            action = "HOLD"
        else:
            if fused > 0.15:
                action = "BUY"
            elif fused < -0.15:
                action = "SELL"
            else:
                action = "HOLD"

        if action == "BUY" and position_qty == 0.0:
            notional = cash * trade_fraction_cash
            if notional <= 0:
                continue
            qty = notional / price
            fee = fee_rate * notional
            cash -= notional + fee
            position_qty = qty
            entry_price = price
            trades.append(
                BacktestTrade(
                    ts=str(ts),
                    symbol=symbol,
                    side="BUY",
                    qty=qty,
                    price=price,
                    fee=fee,
                    pnl=0.0,
                )
            )

        if action == "SELL" and position_qty > 0.0:
            qty = position_qty
            notional = qty * price
            fee = fee_rate * notional
            pnl = (price - entry_price) * qty - fee
            cash += notional - fee
            position_qty = 0.0
            entry_price = 0.0
            trades.append(
                BacktestTrade(
                    ts=str(ts),
                    symbol=symbol,
                    side="SELL",
                    qty=qty,
                    price=price,
                    fee=fee,
                    pnl=float(pnl),
                )
            )

    # Final close if still holding
    if position_qty > 0.0:
        price = float(df["close"].iloc[-1])
        notional = position_qty * price
        fee = fee_rate * notional
        cash += notional - fee
        position_qty = 0.0
        equity[-1] = cash

    metrics = _equity_metrics(equity, periods_per_year=_periods_per_year(interval))
    return BacktestResult(symbol=symbol, interval=interval, metrics=metrics, trades=trades[-200:])

