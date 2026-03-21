from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Iterable, List, Dict

import praw


def _get_reddit() -> praw.Reddit:
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "CryptoVolt/1.0")
    if not client_id or not client_secret:
        raise RuntimeError("Reddit API credentials not set in env (REDDIT_CLIENT_ID/SECRET).")
    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def _symbol_aliases(symbol: str) -> list[str]:
    s = symbol.upper()
    aliases = {s}
    for quote in ("USDT", "BUSD", "USDC", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            aliases.add(s[: -len(quote)])
    return [a for a in aliases if a]


def fetch_symbol_posts(symbols: Iterable[str], limit: int = 100) -> List[Dict]:
    """
    Fetch recent Reddit posts mentioning any of the given symbols from a few crypto subreddits.

    Returns list of dicts with keys:
    - symbol, ts (datetime, UTC), source, title, text, url
    """
    try:
        reddit = _get_reddit()
    except RuntimeError:
        # If credentials are missing, return no posts so callers can fall back to neutral sentiment.
        return []
    subreddits = [
        "CryptoCurrency",
        "CryptoMarkets",
        "cryptotrading",
        "SatoshiStreetBets",
        "altcoin",
        "binance",
    ]
    sym_list = list({s.upper() for s in symbols})
    alias_to_symbols: Dict[str, list[str]] = {}
    for sym in sym_list:
        for alias in _symbol_aliases(sym):
            alias_to_symbols.setdefault(alias, []).append(sym)

    results: List[Dict] = []
    for sub in subreddits:
        for post in reddit.subreddit(sub).new(limit=limit):
            text = f"{post.title}\n\n{post.selftext or ''}"
            upper = text.upper()
            hit_syms: list[str] = []
            for alias, mapped_symbols in alias_to_symbols.items():
                if alias in upper or f"${alias}" in upper:
                    hit_syms.extend(mapped_symbols)
            if not hit_syms:
                continue
            ts = datetime.fromtimestamp(float(post.created_utc), tz=timezone.utc)
            for sym in set(hit_syms):
                results.append(
                    {
                        "symbol": sym,
                        "ts": ts,
                        "source": f"reddit/{sub}",
                        "title": post.title,
                        "text": post.selftext or "",
                        "url": f"https://reddit.com{post.permalink}",
                    }
                )
    return results

