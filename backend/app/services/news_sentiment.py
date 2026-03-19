from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.services.reddit_client import fetch_symbol_posts

_analyzer = SentimentIntensityAnalyzer()


def _floor_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def reddit_sentiment_features(
    symbols: Iterable[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> pd.DataFrame:
    """
    Aggregate Reddit posts into per-(symbol, minute) sentiment features.

    Returns DataFrame with columns:
      ts (datetime, UTC, floored to minute),
      symbol,
      sent_mean,
      sent_count,
      sent_pos_share,
      sent_neg_share.
    """
    sym_list = list({s.upper() for s in symbols})
    if not sym_list:
        return pd.DataFrame(
            columns=["ts", "symbol", "sent_mean", "sent_count", "sent_pos_share", "sent_neg_share"]
        )

    posts = fetch_symbol_posts(sym_list, limit=200)
    rows = []
    start_dt = start.to_pydatetime().astimezone(timezone.utc)
    end_dt = end.to_pydatetime().astimezone(timezone.utc)

    for p in posts:
        ts: datetime = p["ts"]
        if ts < start_dt or ts > end_dt:
            continue
        text = f"{p.get('title','')}\n\n{p.get('text','')}"
        s = _analyzer.polarity_scores(text)
        rows.append(
            {
                "symbol": p["symbol"],
                "ts": _floor_minute(ts),
                "compound": s["compound"],
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["ts", "symbol", "sent_mean", "sent_count", "sent_pos_share", "sent_neg_share"]
        )

    df = pd.DataFrame(rows)
    df["pos"] = (df["compound"] > 0.25).astype(int)
    df["neg"] = (df["compound"] < -0.25).astype(int)

    g = df.groupby(["symbol", "ts"])
    agg = g.agg(
        sent_mean=("compound", "mean"),
        sent_count=("compound", "size"),
        sent_pos_share=("pos", "mean"),
        sent_neg_share=("neg", "mean"),
    ).reset_index()

    return agg

