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


def _sharpe_ratio(
    equity: np.ndarray,
    timestamps: pd.Series | None,
    *,
    periods_per_year_for_bar: float,
) -> float:
    """
    Prefer daily (365d/year crypto) then hourly, then clipped per-bar Sharpe.
    Minute-bar Sharpe is dominated by noise and was producing extreme values (e.g. -150).
    """
    eq = equity.astype(float)

    def _from_returns(
        r: np.ndarray,
        annual_mult: float,
        *,
        min_obs: int,
        max_abs: float,
    ) -> float | None:
        if len(r) < min_obs:
            return None
        sd = float(np.std(r, ddof=1))
        if sd < 1e-12:
            return None
        return float(np.clip(np.mean(r) / sd * np.sqrt(annual_mult), -max_abs, max_abs))

    if timestamps is not None and len(timestamps) == len(eq):
        ts = pd.to_datetime(timestamps, utc=True)
        df = pd.DataFrame({"ts": ts, "eq": eq})
        daily = df.groupby(df["ts"].dt.floor("D"))["eq"].last()
        dr = daily.pct_change().dropna().to_numpy()
        s = _from_returns(dr, 365.0, min_obs=5, max_abs=12.0)
        if s is not None:
            return s
        hourly = df.groupby(df["ts"].dt.floor("h"))["eq"].last()
        hr = hourly.pct_change().dropna().to_numpy()
        s = _from_returns(hr, 24.0 * 365.0, min_obs=12, max_abs=12.0)
        if s is not None:
            return s

    rets = np.diff(eq) / np.maximum(1e-12, eq[:-1])
    s = _from_returns(rets, periods_per_year_for_bar, min_obs=10, max_abs=8.0)
    return 0.0 if s is None else s


def _equity_metrics(
    equity: np.ndarray,
    periods_per_year: float,
    timestamps: pd.Series | None = None,
) -> dict[str, Any]:
    """
    CAGR: geometric annualization is *misleading* for very short windows (e.g. a few hours
    of 1m bars): a small loss compounds to ~-100% when raised to the huge power
    periods_per_year / T. We only report `cagr_like` when the sample spans at least
    `min_years_for_cagr` (default: 7 calendar days implied by bar count).
    """
    eq0 = float(equity[0]) if len(equity) else 0.0
    eq1 = float(equity[-1]) if len(equity) else 0.0
    rets = np.diff(equity) / np.maximum(1e-12, equity[:-1])
    if len(rets) < 1:
        return {
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "final_return": float(eq1 - eq0),
            "total_return_pct": 0.0,
            "period_years": 0.0,
            "cagr_like": None,
            "cagr_annualized": False,
            "cagr_note": "insufficient data",
        }

    peaks = np.maximum.accumulate(equity)
    dd = (equity - peaks) / np.maximum(1e-12, peaks)
    max_dd = float(np.min(dd))

    period_years = float(len(rets)) / float(periods_per_year)
    total_return_pct = float((eq1 / max(1e-12, eq0) - 1.0) * 100.0)

    sharpe = _sharpe_ratio(equity, timestamps, periods_per_year_for_bar=periods_per_year)

    min_years_for_cagr = 7.0 / 365.0
    cagr_note = ""
    cagr_like: float | None
    cagr_annualized = False
    if eq0 <= 0:
        cagr_like = None
        cagr_note = "invalid start equity"
    elif period_years < min_years_for_cagr:
        # Do not annualize tiny windows — show total_return_pct instead in UI.
        cagr_like = None
        cagr_note = (
            f"sample shorter than {min_years_for_cagr * 365:.0f} days; CAGR not shown "
            "(geometric annualization is misleading on intraday windows)"
        )
    else:
        cagr_like = float((eq1 / eq0) ** (1.0 / period_years) - 1.0)
        cagr_annualized = True

    return {
        "sharpe": sharpe,
        "max_drawdown": max_dd,
        "final_return": float(eq1 - eq0),
        "total_return_pct": total_return_pct,
        "period_years": period_years,
        "cagr_like": cagr_like,
        "cagr_annualized": cagr_annualized,
        "cagr_note": cagr_note,
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
    buy_fused_threshold: float = 0.15,
    sell_fused_threshold: float = -0.15,
    use_proba_thresholds: bool = False,
    buy_proba_threshold: float = 0.55,
    sell_proba_threshold: float = 0.45,
    # Risk management in basis points (bps). Set to 0 to disable.
    stop_loss_bps: float = 0.0,
    take_profit_bps: float = 0.0,
    trailing_stop_bps: float = 0.0,
    max_drawdown_limit: float = 0.05,
) -> BacktestResult:
    """
    Long-only backtest:
      - BUY when fused score > buy_fused_threshold and no position
      - SELL when fused score < sell_fused_threshold and position exists
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

    peak_price = 0.0
    halted = False

    for i in range(len(df)):
        ts = df["ts"].iloc[i]
        price = float(df["close"].iloc[i])

        # Mark-to-market equity
        equity[i] = cash + position_qty * price
        # Hard risk brake: stop simulation when drawdown breaches limit.
        # WHY: protects against prolonged model drift on bad symbols.
        peak_equity = float(np.max(equity[: i + 1]))
        if peak_equity > 0:
            dd_now = (equity[i] - peak_equity) / peak_equity
            if max_drawdown_limit > 0 and dd_now <= -float(max_drawdown_limit):
                halted = True
                if position_qty > 0.0:
                    notional = position_qty * price
                    fee = fee_rate * notional
                    cash += notional - fee
                    position_qty = 0.0
                    entry_price = 0.0
                equity[i:] = cash
                break

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
            if use_proba_thresholds:
                if proba_up >= buy_proba_threshold:
                    action = "BUY"
                elif proba_up <= sell_proba_threshold:
                    action = "SELL"
                else:
                    action = "HOLD"
            else:
                if fused > buy_fused_threshold:
                    action = "BUY"
                elif fused < sell_fused_threshold:
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
            peak_price = price
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

        # Risk management overrides (reduce maximum loss).
        if position_qty > 0.0:
            # Unrealized PnL threshold checks vs entry.
            if stop_loss_bps > 0.0:
                stop_price = entry_price * (1.0 - stop_loss_bps / 10_000.0)
                if price <= stop_price:
                    action = "SELL"
            if take_profit_bps > 0.0 and action != "SELL":
                tp_price = entry_price * (1.0 + take_profit_bps / 10_000.0)
                if price >= tp_price:
                    action = "SELL"

            # Trailing stop checks vs peak.
            if trailing_stop_bps > 0.0 and action != "SELL":
                peak_price = max(peak_price, price)
                trail_price = peak_price * (1.0 - trailing_stop_bps / 10_000.0)
                if price <= trail_price:
                    action = "SELL"
            elif trailing_stop_bps <= 0.0:
                # Keep peak_price consistent even if trailing_stop disabled.
                peak_price = max(peak_price, price)

        if action == "SELL" and position_qty > 0.0:
            qty = position_qty
            notional = qty * price
            fee = fee_rate * notional
            pnl = (price - entry_price) * qty - fee
            cash += notional - fee
            position_qty = 0.0
            entry_price = 0.0
            peak_price = 0.0
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

    metrics = _equity_metrics(
        equity,
        periods_per_year=_periods_per_year(interval),
        timestamps=df["ts"],
    )
    metrics["halted_on_max_dd"] = halted
    metrics["max_drawdown_limit"] = float(max_drawdown_limit)
    return BacktestResult(symbol=symbol, interval=interval, metrics=metrics, trades=trades[-200:])

