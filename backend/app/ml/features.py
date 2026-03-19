from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD
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

