from __future__ import annotations

import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD, ADXIndicator
from ta.volatility import BollingerBands


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Input df columns: ts, open, high, low, close, volume
    Returns df with feature columns, without NaNs.
    """
    out = df.copy()

    # Price returns
    out["ret_1"] = out["close"].pct_change(1)
    out["ret_3"] = out["close"].pct_change(3)
    out["ret_5"] = out["close"].pct_change(5)

    # Trend
    out["ema_12"] = EMAIndicator(out["close"], window=12).ema_indicator()
    out["ema_26"] = EMAIndicator(out["close"], window=26).ema_indicator()
    out["ema_diff"] = (out["ema_12"] - out["ema_26"]) / out["close"]

    # MACD
    macd = MACD(out["close"], window_slow=26, window_fast=12, window_sign=9)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_hist"] = macd.macd_diff()

    # RSI
    out["rsi_14"] = RSIIndicator(out["close"], window=14).rsi()

    # Bollinger Bands
    bb = BollingerBands(out["close"], window=20, window_dev=2)
    out["bb_mavg"] = bb.bollinger_mavg()
    out["bb_hband"] = bb.bollinger_hband()
    out["bb_lband"] = bb.bollinger_lband()
    out["bb_width"] = (out["bb_hband"] - out["bb_lband"]) / out["close"]

    # Volatility regime features.
    # WHY: Regime-aware models avoid over-trading in noisy/high-volatility windows.
    out["vol_20"] = out["ret_1"].rolling(20).std()
    out["vol_60"] = out["ret_1"].rolling(60).std()
    out["vol_regime"] = out["vol_20"] / out["vol_60"].replace(0.0, np.nan)

    # Trend strength (ADX) + directional pressure.
    # WHY: Captures whether a move is likely to persist (trend) vs mean-revert (chop).
    adx = ADXIndicator(out["high"], out["low"], out["close"], window=14)
    out["adx_14"] = adx.adx()
    out["trend_strength"] = out["adx_14"] * np.sign(out["ema_diff"].fillna(0.0))

    # Volume normalization.
    # WHY: Relative volume is more stable across coins than raw absolute volume.
    out["volume_z20"] = (
        (out["volume"] - out["volume"].rolling(20).mean())
        / out["volume"].rolling(20).std().replace(0.0, np.nan)
    )

    # Interaction features.
    # WHY: Trading edges often come from interactions (momentum x trend x liquidity).
    out["rsi_x_trend"] = out["rsi_14"] * out["ema_diff"]
    out["macd_hist_x_vol"] = out["macd_hist"] * out["vol_regime"]
    out["ret1_x_volume_z"] = out["ret_1"] * out["volume_z20"]

    out = out.dropna().reset_index(drop=True)
    return out


def build_labels(df: pd.DataFrame, *, horizon: int = 1, threshold: float = 0.0) -> pd.Series:
    """
    Binary classification label: 1 if future return > threshold else 0.
    """
    future = df["close"].shift(-horizon)
    ret = (future - df["close"]) / df["close"]
    y = (ret > threshold).astype(int)
    return y


def build_trading_labels(
    df: pd.DataFrame,
    *,
    horizon: int = 1,
    base_threshold: float = 0.0,
    method: str = "vol_cost",
    cost_bps: float = 4.0,
    vol_mult: float = 0.35,
    pt_sl_mult: float = 1.2,
) -> tuple[pd.Series, pd.Series]:
    """
    Trading-aware labels and aligned forward returns.

    Methods:
      - "simple": y=1 if forward return > base_threshold.
      - "vol_cost": y=1 if forward return > (cost + vol-adjusted threshold).
      - "triple_barrier": y=1 if TP barrier hits before SL within horizon.
    """
    future = df["close"].shift(-horizon)
    fwd_ret = (future - df["close"]) / df["close"]

    if method == "simple":
        y = (fwd_ret > base_threshold).astype(int)
        return y, fwd_ret

    if method == "triple_barrier":
        rolling_vol = df["close"].pct_change().rolling(20).std().fillna(0.0)
        up = df["close"] * (1.0 + (pt_sl_mult * rolling_vol + cost_bps / 10_000.0))
        dn = df["close"] * (1.0 - (pt_sl_mult * rolling_vol + cost_bps / 10_000.0))
        y = pd.Series(0, index=df.index, dtype=int)
        for i in range(len(df)):
            end = min(i + horizon, len(df) - 1)
            if i >= end:
                y.iloc[i] = 0
                continue
            path_h = df["high"].iloc[i + 1 : end + 1]
            path_l = df["low"].iloc[i + 1 : end + 1]
            hit_up = path_h[path_h >= up.iloc[i]]
            hit_dn = path_l[path_l <= dn.iloc[i]]
            if len(hit_up) == 0 and len(hit_dn) == 0:
                y.iloc[i] = int(fwd_ret.iloc[i] > 0.0)
            elif len(hit_up) > 0 and len(hit_dn) == 0:
                y.iloc[i] = 1
            elif len(hit_up) == 0 and len(hit_dn) > 0:
                y.iloc[i] = 0
            else:
                y.iloc[i] = int(hit_up.index[0] < hit_dn.index[0])
        return y, fwd_ret

    # Default: volatility + cost-aware threshold.
    rolling_vol = df["close"].pct_change().rolling(20).std().fillna(0.0)
    dyn_th = base_threshold + (cost_bps / 10_000.0) + vol_mult * rolling_vol
    y = (fwd_ret > dyn_th).astype(int)
    return y, fwd_ret

