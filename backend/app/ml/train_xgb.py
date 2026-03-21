from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, precision_score, recall_score
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, TimeSeriesSplit, train_test_split
from xgboost import XGBClassifier
from scipy.stats import randint, uniform

from app.ml.features import build_features, build_trading_labels
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
    "vol_20",
    "vol_60",
    "vol_regime",
    "adx_14",
    "trend_strength",
    "volume_z20",
    "rsi_x_trend",
    "macd_hist_x_vol",
    "ret1_x_volume_z",
    "sent_mean",
    "sent_count",
    "sent_pos_share",
    "sent_neg_share",
]

DATASET_DIR = Path(os.getenv("CRYPTOVOLT_DATA_DIR", "D:/CryptoVolt/backend/_datasets"))
DATASET_DIR.mkdir(parents=True, exist_ok=True)

def _best_threshold(y_true: np.ndarray, proba: np.ndarray) -> tuple[float, float]:
    """
    Backwards-compatible helper: returns (best_threshold, best_f1) on provided
    labels/probabilities.
    """
    return _best_threshold_metric(y_true, proba, metric="f1")


def _best_threshold_metric(
    y_true: np.ndarray,
    proba: np.ndarray,
    *,
    metric: Literal["f1", "accuracy"] = "f1",
) -> tuple[float, float]:
    """
    Pick a probability threshold that maximizes the chosen metric on (y_true, proba).
    """
    best_t = 0.5
    best_val = -1.0
    # Coarse grid is usually enough for trading signals.
    for t in np.linspace(0.1, 0.9, 41):
        pred = (proba >= t).astype(int)
        if metric == "accuracy":
            val = float((pred == y_true).mean())
        else:
            val = float(f1_score(y_true, pred, zero_division=0))
        if val > best_val:
            best_val = val
            best_t = float(t)
    return best_t, best_val


def _best_threshold_profit(
    proba: np.ndarray,
    future_ret: np.ndarray,
    *,
    fee_bps: float = 4.0,
) -> tuple[float, float]:
    """
    Select threshold maximizing expected net PnL on validation.
    """
    best_t = 0.5
    best_pnl = -1e18
    fee = float(fee_bps) / 10_000.0
    for t in np.linspace(0.05, 0.95, 91):
        long_mask = proba >= t
        if not np.any(long_mask):
            pnl = -1e9
        else:
            pnl = float(np.sum(future_ret[long_mask] - fee))
        if pnl > best_pnl:
            best_pnl = pnl
            best_t = float(t)
    return best_t, best_pnl


def _best_threshold_sharpe(
    proba: np.ndarray,
    future_ret: np.ndarray,
    *,
    fee_bps: float = 4.0,
) -> tuple[float, float]:
    """
    Select threshold maximizing Sharpe-like ratio on validation trade stream.
    """
    best_t = 0.5
    best_sharpe = -1e18
    fee = float(fee_bps) / 10_000.0
    for t in np.linspace(0.05, 0.95, 91):
        long_mask = proba >= t
        if not np.any(long_mask):
            sharpe_like = -1e9
        else:
            trade_ret = future_ret[long_mask] - fee
            std = float(np.std(trade_ret))
            sharpe_like = float(np.mean(trade_ret) / std) if std > 1e-12 else -1e9
        if sharpe_like > best_sharpe:
            best_sharpe = sharpe_like
            best_t = float(t)
    return best_t, best_sharpe


def _trade_metrics_from_preds(
    pred: np.ndarray,
    future_ret: np.ndarray,
    *,
    fee_bps: float = 4.0,
) -> dict[str, float]:
    """
    Compute trading-oriented metrics from binary trade decisions.
    """
    fee = float(fee_bps) / 10_000.0
    trade_ret = np.where(pred == 1, future_ret - fee, 0.0)
    trades = np.count_nonzero(pred == 1)
    gross_pnl = float(np.sum(trade_ret))
    avg_trade = float(np.mean(trade_ret[pred == 1])) if trades > 0 else 0.0
    win_rate = float(np.mean((trade_ret[pred == 1]) > 0.0)) if trades > 0 else 0.0
    # Naive equity curve for drawdown approximation on decision stream.
    equity = 1.0 + np.cumsum(trade_ret)
    peaks = np.maximum.accumulate(equity)
    dd = (equity - peaks) / np.maximum(peaks, 1e-12)
    max_dd = float(np.min(dd)) if len(dd) > 0 else 0.0
    return {
        "trades": float(trades),
        "gross_pnl": gross_pnl,
        "avg_trade_return": avg_trade,
        "win_rate": win_rate,
        "max_drawdown_like": max_dd,
    }


def _walk_forward_profit_score(
    X: pd.DataFrame,
    y: pd.Series,
    future_ret: pd.Series,
    params: dict[str, Any],
) -> dict[str, float]:
    """
    Time-ordered validation to estimate out-of-sample trading behavior.
    """
    tscv = TimeSeriesSplit(n_splits=4)
    fold_pnl: list[float] = []
    fold_win: list[float] = []
    for tr_idx, va_idx in tscv.split(X):
        X_tr, X_va = X.iloc[tr_idx], X.iloc[va_idx]
        y_tr, y_va = y.iloc[tr_idx], y.iloc[va_idx]
        fwd_va = future_ret.iloc[va_idx].to_numpy()
        model = XGBClassifier(**params)
        model.fit(X_tr, y_tr)
        proba = model.predict_proba(X_va)[:, 1]
        t, _ = _best_threshold_profit(proba, fwd_va)
        pred = (proba >= t).astype(int)
        tm = _trade_metrics_from_preds(pred, fwd_va)
        fold_pnl.append(tm["gross_pnl"])
        fold_win.append(tm["win_rate"])
    return {
        "wf_avg_pnl": float(np.mean(fold_pnl)) if fold_pnl else 0.0,
        "wf_avg_win_rate": float(np.mean(fold_win)) if fold_win else 0.0,
    }


async def _load_symbol(
    symbol: str,
    interval: str,
    limit: int,
    *,
    label_horizon: int,
    label_threshold: float,
    label_method: Literal["simple", "vol_cost", "triple_barrier"],
    label_cost_bps: float,
    label_vol_mult: float,
    label_pt_sl_mult: float,
    sentiment_post_limit: int,
) -> tuple[pd.DataFrame, dict[str, float]]:
    df = await fetch_klines(KlineQuery(symbol=symbol, interval=interval, limit=limit))
    df["symbol"] = symbol
    feats = build_features(df)

    # join Reddit sentiment features on (symbol, ts)
    if not feats.empty:
        sent = reddit_sentiment_features(
            symbols=[symbol],
            start=feats["ts"].min(),
            end=feats["ts"].max(),
            post_limit=sentiment_post_limit,
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

    y, fwd_ret = build_trading_labels(
        feats,
        horizon=label_horizon,
        base_threshold=label_threshold,
        method=label_method,
        cost_bps=label_cost_bps,
        vol_mult=label_vol_mult,
        pt_sl_mult=label_pt_sl_mult,
    )
    # Drop the last `label_horizon` rows since future returns become NaN there.
    # This keeps (X, y) aligned and prevents trailing rows from being
    # implicitly labeled as 0 due to NaN comparisons.
    if label_horizon > 0:
        feats = feats.iloc[:-label_horizon].copy()
        y = y.iloc[:-label_horizon].copy()
        fwd_ret = fwd_ret.iloc[:-label_horizon].copy()
    feats["y"] = y.values
    feats["future_ret"] = fwd_ret.values
    sent_cov = 0.0
    if len(feats) > 0 and "sent_count" in feats.columns:
        sent_cov = float((feats["sent_count"] > 0).mean())
    return feats, {"sentiment_coverage": sent_cov}


async def train_xgb_multi(
    *,
    symbols: list[str],
    interval: str = "1m",
    limit_per_symbol: int = 750,
    random_state: int = 42,
    tune: bool = False,
    tune_trials: int = 25,
    optimize_metric: Literal["roc_auc", "accuracy", "f1", "profit", "sharpe"] = "roc_auc",
    label_horizon: int = 1,
    label_threshold: float = 0.0,
    label_method: Literal["simple", "vol_cost", "triple_barrier"] = "vol_cost",
    label_cost_bps: float = 4.0,
    label_vol_mult: float = 0.35,
    label_pt_sl_mult: float = 1.2,
    sentiment_post_limit: int = 200,
    sentiment_required: bool = False,
    min_sentiment_coverage: float = 0.02,
) -> TrainResult:
    # Load data concurrently but limit concurrency to avoid hammering API.
    sem = asyncio.Semaphore(5)

    async def guarded(sym: str):
        async with sem:
            return await _load_symbol(
                sym,
                interval,
                limit_per_symbol,
                label_horizon=label_horizon,
                label_threshold=label_threshold,
                label_method=label_method,
                label_cost_bps=label_cost_bps,
                label_vol_mult=label_vol_mult,
                label_pt_sl_mult=label_pt_sl_mult,
                sentiment_post_limit=sentiment_post_limit,
            )

    frames = await asyncio.gather(*[guarded(s) for s in symbols], return_exceptions=True)
    good: list[pd.DataFrame] = []
    sentiment_coverages: list[float] = []
    for f in frames:
        if isinstance(f, Exception):
            continue
        feats, meta = f
        if len(feats) < 80:
            continue
        cov = float(meta.get("sentiment_coverage", 0.0))
        if sentiment_required and cov < float(min_sentiment_coverage):
            continue
        good.append(feats)
        sentiment_coverages.append(cov)

    if not good:
        raise RuntimeError("No usable symbol data fetched for training.")

    data = pd.concat(good, ignore_index=True)

    # Persist combined training dataset to CSV for analysis.
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    csv_path = DATASET_DIR / f"xgb_dataset_{interval}_{ts}.csv"
    data.to_csv(csv_path, index=False)
    X = data[FEATURE_COLS].astype(np.float32)
    y = data["y"].astype(int)
    future_ret = data["future_ret"].astype(np.float32)

    X_train_full, X_test, y_train_full, y_test, fwd_train_full, fwd_test = train_test_split(
        X, y, future_ret, test_size=0.2, random_state=random_state, stratify=y
    )
    # Validation split for threshold tuning (and tuning selection sanity).
    X_train, X_val, y_train, y_val, fwd_train, fwd_val = train_test_split(
        X_train_full, y_train_full, fwd_train_full, test_size=0.2, random_state=random_state, stratify=y_train_full
    )

    pos = float(np.sum(y_train_full))
    neg = float(len(y_train_full) - pos)
    scale_pos_weight = (neg / pos) if pos > 0 else 1.0
    # How much accuracy you can get even with a dumb classifier (predicting
    # only the majority class) on the test split.
    pos_rate_test = float(np.mean(y_test))
    majority_accuracy = float(max(pos_rate_test, 1.0 - pos_rate_test))

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
        "scale_pos_weight": float(scale_pos_weight),
    }

    # Baseline fit + eval (always)
    baseline_model = XGBClassifier(**base_params)
    baseline_model.fit(X_train, y_train)
    base_val_proba = baseline_model.predict_proba(X_val)[:, 1]
    y_val_np = y_val.to_numpy()

    base_best_f1_t, base_val_f1 = _best_threshold_metric(
        y_val_np, base_val_proba, metric="f1"
    )
    base_best_acc_t, base_val_acc = _best_threshold_metric(
        y_val_np, base_val_proba, metric="accuracy"
    )

    base_best_profit_t, base_val_profit = _best_threshold_profit(
        base_val_proba, fwd_val.to_numpy(), fee_bps=label_cost_bps
    )
    base_best_sharpe_t, base_val_sharpe = _best_threshold_sharpe(
        base_val_proba, fwd_val.to_numpy(), fee_bps=label_cost_bps
    )
    # Choose threshold by requested objective.
    if optimize_metric == "accuracy":
        base_t = base_best_acc_t
    elif optimize_metric == "profit":
        base_t = base_best_profit_t
    elif optimize_metric == "sharpe":
        base_t = base_best_sharpe_t
    else:
        base_t = base_best_f1_t

    base_proba = baseline_model.predict_proba(X_test)[:, 1]
    base_pred = (base_proba >= base_t).astype(int)
    base_trade = _trade_metrics_from_preds(base_pred, fwd_test.to_numpy(), fee_bps=label_cost_bps)
    baseline_metrics = {
        "auc": float(roc_auc_score(y_test, base_proba)),
        "accuracy": float(accuracy_score(y_test, base_pred)),
        "precision": float(precision_score(y_test, base_pred, zero_division=0)),
        "recall": float(recall_score(y_test, base_pred, zero_division=0)),
        "f1": float(f1_score(y_test, base_pred, zero_division=0)),
        "threshold": float(base_t),
        "val_f1": float(base_val_f1),
        "val_accuracy": float(base_val_acc),
        "val_profit": float(base_val_profit),
        "val_sharpe": float(base_val_sharpe),
        **base_trade,
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

        def _tune_scorer(estimator_for_fold, X_fold, y_fold):
            # Tune via best-threshold selection on the fold.
            proba = estimator_for_fold.predict_proba(X_fold)[:, 1]
            y_fold_np = np.asarray(y_fold)
            _, best_val = _best_threshold_metric(
                y_fold_np,
                proba,
                metric=("accuracy" if optimize_metric == "accuracy" else "f1"),
            )
            return best_val

        tune_scoring: Any = "roc_auc"
        if optimize_metric in ("accuracy", "f1"):
            tune_scoring = _tune_scorer

        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=search_space,
            n_iter=max(5, int(tune_trials)),
            scoring=tune_scoring,
            cv=cv,
            n_jobs=1,
            random_state=random_state,
            verbose=0,
        )
        search.fit(X_train, y_train)
        tuned_model = search.best_estimator_
        tuned_params = {**base_params, **search.best_params_}

        tuned_val_proba = tuned_model.predict_proba(X_val)[:, 1]
        tuned_best_f1_t, tuned_val_f1 = _best_threshold_metric(
            y_val_np, tuned_val_proba, metric="f1"
        )
        tuned_best_acc_t, tuned_val_acc = _best_threshold_metric(
            y_val_np, tuned_val_proba, metric="accuracy"
        )
        tuned_best_profit_t, tuned_val_profit = _best_threshold_profit(
            tuned_val_proba, fwd_val.to_numpy(), fee_bps=label_cost_bps
        )
        tuned_best_sharpe_t, tuned_val_sharpe = _best_threshold_sharpe(
            tuned_val_proba, fwd_val.to_numpy(), fee_bps=label_cost_bps
        )

        if optimize_metric == "accuracy":
            tuned_t = tuned_best_acc_t
        elif optimize_metric == "profit":
            tuned_t = tuned_best_profit_t
        elif optimize_metric == "sharpe":
            tuned_t = tuned_best_sharpe_t
        else:
            tuned_t = tuned_best_f1_t

        tuned_proba = tuned_model.predict_proba(X_test)[:, 1]
        tuned_pred = (tuned_proba >= tuned_t).astype(int)
        tuned_trade = _trade_metrics_from_preds(tuned_pred, fwd_test.to_numpy(), fee_bps=label_cost_bps)
        tuned_metrics = {
            "auc": float(roc_auc_score(y_test, tuned_proba)),
            "accuracy": float(accuracy_score(y_test, tuned_pred)),
            "precision": float(precision_score(y_test, tuned_pred, zero_division=0)),
            "recall": float(recall_score(y_test, tuned_pred, zero_division=0)),
            "f1": float(f1_score(y_test, tuned_pred, zero_division=0)),
            "threshold": float(tuned_t),
            "val_f1": float(tuned_val_f1),
            "val_accuracy": float(tuned_val_acc),
            "val_profit": float(tuned_val_profit),
            "val_sharpe": float(tuned_val_sharpe),
            **tuned_trade,
        }

        tuning_details = {
            "best_cv_auc": float(search.best_score_),
            "trials": int(search.n_iter),
            "baseline": baseline_metrics,
            "tuned": tuned_metrics,
        }

        # Keep tuned model only if it improves the requested metric.
        if optimize_metric == "accuracy":
            better = (tuned_metrics["accuracy"] > baseline_metrics["accuracy"]) or (
                tuned_metrics["accuracy"] == baseline_metrics["accuracy"]
                and tuned_metrics["f1"] > baseline_metrics["f1"]
            )
        elif optimize_metric == "profit":
            better = (tuned_metrics["gross_pnl"] > baseline_metrics["gross_pnl"]) or (
                tuned_metrics["gross_pnl"] == baseline_metrics["gross_pnl"]
                and tuned_metrics["max_drawdown_like"] >= baseline_metrics["max_drawdown_like"]
            )
        elif optimize_metric == "sharpe":
            better = (tuned_metrics["val_sharpe"] > baseline_metrics["val_sharpe"]) or (
                tuned_metrics["val_sharpe"] == baseline_metrics["val_sharpe"]
                and tuned_metrics["gross_pnl"] >= baseline_metrics["gross_pnl"]
            )
        elif optimize_metric == "f1":
            better = (tuned_metrics["f1"] > baseline_metrics["f1"]) or (
                tuned_metrics["f1"] == baseline_metrics["f1"]
                and tuned_metrics["auc"] >= baseline_metrics["auc"]
            )
        else:
            # roc_auc
            better = (tuned_metrics["auc"] > baseline_metrics["auc"]) or (
                tuned_metrics["auc"] == baseline_metrics["auc"]
                and tuned_metrics["f1"] > baseline_metrics["f1"]
            )

        if better:
            chosen_model = tuned_model
            chosen_params = tuned_params
            chosen_metrics = tuned_metrics
            selected = "tuned"

    wf_metrics = _walk_forward_profit_score(
        X_train_full,
        y_train_full,
        fwd_train_full,
        chosen_params,
    )
    final_metrics = {
        **chosen_metrics,
        "n_samples": int(len(data)),
        "n_symbols": int(len(good)),
        "sentiment_coverage_mean": float(np.mean(sentiment_coverages)) if sentiment_coverages else 0.0,
        "selected": selected,
        "dataset_path": str(csv_path),
        "pos_rate_test": pos_rate_test,
        "majority_accuracy": majority_accuracy,
        "label_method": label_method,
        "label_cost_bps": label_cost_bps,
        "label_vol_mult": label_vol_mult,
        "label_pt_sl_mult": label_pt_sl_mult,
        **wf_metrics,
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

