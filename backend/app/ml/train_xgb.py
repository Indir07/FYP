from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from xgboost import XGBClassifier
from scipy.stats import randint, uniform

from app.ml.features import build_features, build_labels
from app.services.binance_market import KlineQuery, fetch_klines
from app.services.news_sentiment import reddit_sentiment_features

from pathlib import Path
import os
from datetime import datetime, timezone


@dataclass(frozen=True)
class TrainResult:
    model: Any
    metrics: dict
    params: dict
    symbols: list[str]
    interval: str


FEATURE_COLS = [
    "ret_1",
    "ret_3",
    "ret_5",
    "ema_diff",
    "macd",
    "macd_signal",
    "macd_hist",
    "rsi_14",
    "bb_width",
    "volume",
    "sent_mean",
    "sent_count",
    "sent_pos_share",
    "sent_neg_share",
]

DATASET_DIR = Path(os.getenv("CRYPTOVOLT_DATA_DIR", "D:/CryptoVolt/backend/_datasets"))
DATASET_DIR.mkdir(parents=True, exist_ok=True)

def _best_threshold(y_true: np.ndarray, proba: np.ndarray) -> tuple[float, float]:
    """
    Returns (threshold, best_f1) tuned on provided labels/probabilities.
    """
    best_t = 0.5
    best_f1 = -1.0
    # Coarse grid is usually enough for trading signals.
    for t in np.linspace(0.2, 0.8, 25):
        pred = (proba >= t).astype(int)
        f1 = float(f1_score(y_true, pred, zero_division=0))
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
    return best_t, best_f1


async def _load_symbol(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    df = await fetch_klines(KlineQuery(symbol=symbol, interval=interval, limit=limit))
    df["symbol"] = symbol
    feats = build_features(df)

    # join Reddit sentiment features on (symbol, ts)
    if not feats.empty:
        sent = reddit_sentiment_features(
            symbols=[symbol],
            start=feats["ts"].min(),
            end=feats["ts"].max(),
        )
        if not sent.empty:
            feats = feats.merge(sent, on=["symbol", "ts"], how="left")

    # fill missing sentiment values with neutral defaults
    for col, default in [
        ("sent_mean", 0.0),
        ("sent_count", 0.0),
        ("sent_pos_share", 0.0),
        ("sent_neg_share", 0.0),
    ]:
        if col not in feats.columns:
            feats[col] = default
        else:
            feats[col] = feats[col].fillna(default)

    y = build_labels(feats, horizon=1, threshold=0.0)
    feats = feats.iloc[:-1].copy()
    y = y.iloc[:-1].copy()
    feats["y"] = y.values
    return feats


async def train_xgb_multi(
    *,
    symbols: list[str],
    interval: str = "1m",
    limit_per_symbol: int = 750,
    random_state: int = 42,
    tune: bool = False,
    tune_trials: int = 25,
) -> TrainResult:
    # Load data concurrently but limit concurrency to avoid hammering API.
    sem = asyncio.Semaphore(5)

    async def guarded(sym: str):
        async with sem:
            return await _load_symbol(sym, interval, limit_per_symbol)

    frames = await asyncio.gather(*[guarded(s) for s in symbols], return_exceptions=True)
    good: list[pd.DataFrame] = []
    for f in frames:
        if isinstance(f, Exception):
            continue
        if len(f) < 80:
            continue
        good.append(f)

    if not good:
        raise RuntimeError("No usable symbol data fetched for training.")

    data = pd.concat(good, ignore_index=True)

    # Persist combined training dataset to CSV for analysis.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = DATASET_DIR / f"xgb_dataset_{interval}_{ts}.csv"
    data.to_csv(csv_path, index=False)
    X = data[FEATURE_COLS].astype(np.float32)
    y = data["y"].astype(int)

    X_train_full, X_test, y_train_full, y_test = train_test_split(
        X, y, test_size=0.2, random_state=random_state, stratify=y
    )
    # Validation split for threshold tuning (and tuning selection sanity).
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.2, random_state=random_state, stratify=y_train_full
    )

    base_params = {
        "n_estimators": 300,
        "max_depth": 5,
        "learning_rate": 0.05,
        "subsample": 0.9,
        "colsample_bytree": 0.9,
        "reg_lambda": 1.0,
        "objective": "binary:logistic",
        "eval_metric": "logloss",
        "random_state": random_state,
        "tree_method": "hist",
    }

    # Baseline fit + eval (always)
    baseline_model = XGBClassifier(**base_params)
    baseline_model.fit(X_train, y_train)
    base_val_proba = baseline_model.predict_proba(X_val)[:, 1]
    base_t, base_val_f1 = _best_threshold(y_val.to_numpy(), base_val_proba)

    base_proba = baseline_model.predict_proba(X_test)[:, 1]
    base_pred = (base_proba >= base_t).astype(int)
    baseline_metrics = {
        "auc": float(roc_auc_score(y_test, base_proba)),
        "accuracy": float(accuracy_score(y_test, base_pred)),
        "precision": float(precision_score(y_test, base_pred, zero_division=0)),
        "recall": float(recall_score(y_test, base_pred, zero_division=0)),
        "f1": float(f1_score(y_test, base_pred, zero_division=0)),
        "threshold": float(base_t),
        "val_f1": float(base_val_f1),
    }

    chosen_model = baseline_model
    chosen_params = dict(base_params)
    chosen_metrics = dict(baseline_metrics)
    selected = "baseline"
    tuning_details = None

    if tune:
        # Tune on training split only; keep test split strictly held-out.
        search_space = {
            "n_estimators": randint(200, 900),
            "max_depth": randint(3, 9),
            "learning_rate": uniform(0.01, 0.15),
            "subsample": uniform(0.6, 0.4),
            "colsample_bytree": uniform(0.6, 0.4),
            "min_child_weight": randint(1, 12),
            "reg_lambda": uniform(0.0, 3.0),
            "gamma": uniform(0.0, 2.0),
        }
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=random_state)
        estimator = XGBClassifier(**base_params)
        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=search_space,
            n_iter=max(5, int(tune_trials)),
            scoring="roc_auc",
            cv=cv,
            n_jobs=1,
            random_state=random_state,
            verbose=0,
        )
        search.fit(X_train, y_train)
        tuned_model = search.best_estimator_
        tuned_params = {**base_params, **search.best_params_}

        tuned_val_proba = tuned_model.predict_proba(X_val)[:, 1]
        tuned_t, tuned_val_f1 = _best_threshold(y_val.to_numpy(), tuned_val_proba)

        tuned_proba = tuned_model.predict_proba(X_test)[:, 1]
        tuned_pred = (tuned_proba >= tuned_t).astype(int)
        tuned_metrics = {
            "auc": float(roc_auc_score(y_test, tuned_proba)),
            "accuracy": float(accuracy_score(y_test, tuned_pred)),
            "precision": float(precision_score(y_test, tuned_pred, zero_division=0)),
            "recall": float(recall_score(y_test, tuned_pred, zero_division=0)),
            "f1": float(f1_score(y_test, tuned_pred, zero_division=0)),
            "threshold": float(tuned_t),
            "val_f1": float(tuned_val_f1),
        }

        tuning_details = {
            "best_cv_auc": float(search.best_score_),
            "trials": int(search.n_iter),
            "baseline": baseline_metrics,
            "tuned": tuned_metrics,
        }

        # Keep tuned model only if it improves held-out AUC, or equal AUC but better F1.
        if (tuned_metrics["auc"] > baseline_metrics["auc"]) or (
            tuned_metrics["auc"] == baseline_metrics["auc"] and tuned_metrics["f1"] > baseline_metrics["f1"]
        ):
            chosen_model = tuned_model
            chosen_params = tuned_params
            chosen_metrics = tuned_metrics
            selected = "tuned"

    final_metrics = {
        **chosen_metrics,
        "n_samples": int(len(data)),
        "n_symbols": int(len(good)),
        "selected": selected,
        "dataset_path": str(csv_path),
    }
    if tuning_details is not None:
        final_metrics["tuning"] = tuning_details

    return TrainResult(
        model=chosen_model,
        metrics=final_metrics,
        params=chosen_params,
        symbols=[*{d["symbol"].iloc[0] for d in good}],
        interval=interval,
    )

