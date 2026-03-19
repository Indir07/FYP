from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
import joblib

from app.ml.features import build_features
from app.ml.train_xgb import FEATURE_COLS


@dataclass(frozen=True)
class Decision:
    action: Literal["BUY", "SELL", "HOLD"]
    confidence: float
    vetoed: bool
    reason: str


def _rule_signal(df: pd.DataFrame) -> float:
    """
    Simple, interpretable rule score in [-1, 1]:
    - RSI oversold => positive
    - RSI overbought => negative
    - MACD histogram sign contributes mildly
    """
    last = df.iloc[-1]
    score = 0.0
    rsi = float(last.get("rsi_14", 50.0))
    macd_hist = float(last.get("macd_hist", 0.0))
    if rsi < 30:
        score += 0.6
    elif rsi > 70:
        score -= 0.6
    score += float(np.tanh(macd_hist) * 0.4)
    return float(max(-1.0, min(1.0, score)))


def decide(
    *,
    model_path: str,
    ohlcv: pd.DataFrame,
    sentiment_index: float,
    rules_weight: float = 0.45,
    ml_weight: float = 0.55,
    veto_threshold: float = -0.35,
) -> Decision:
    feats = build_features(ohlcv)
    if len(feats) < 50:
        return Decision(action="HOLD", confidence=0.0, vetoed=False, reason="insufficient_data")

    rule_score = _rule_signal(feats)  # [-1, 1]

    model = joblib.load(model_path)
    X = feats[FEATURE_COLS].astype("float32").iloc[[-1]]
    proba_up = float(model.predict_proba(X)[0][1])

    # Map ML proba to [-1, 1]
    ml_score = (proba_up - 0.5) * 2.0
    fused = (rules_weight * rule_score) + (ml_weight * ml_score)

    vetoed = sentiment_index <= veto_threshold
    if vetoed:
        return Decision(action="HOLD", confidence=abs(fused), vetoed=True, reason="sentiment_veto")

    if fused > 0.15:
        return Decision(action="BUY", confidence=abs(fused), vetoed=False, reason="fused_buy")
    if fused < -0.15:
        return Decision(action="SELL", confidence=abs(fused), vetoed=False, reason="fused_sell")
    return Decision(action="HOLD", confidence=abs(fused), vetoed=False, reason="fused_hold")

