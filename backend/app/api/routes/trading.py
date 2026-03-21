from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel
from pydantic import Field

from app.ml.registry import list_entries
from app.services.binance_market import KlineQuery, fetch_klines
from app.services.news_sentiment import reddit_sentiment_features
from app.trading.decision import decide
from app.services.alerts_service import record_alert
from app.trading.paper_broker_instance import broker as _broker

router = APIRouter()

_state = {"automation": False}
_automation_task: asyncio.Task[None] | None = None
_automation_cfg: dict[str, Any] = {
    "symbol": None,
    "interval": "1m",
    "limit": 200,
    "qty": 1.0,
    "rules_weight": 0.45,
    "ml_weight": 0.55,
    "veto_threshold": -0.35,
    "tick_seconds": 30,
    "sentiment_lookback_minutes": 60,
    # Risk management (bps). Set to 0 to disable.
    "stop_loss_bps": 250.0,
    "take_profit_bps": 400.0,
    "trailing_stop_bps": 0.0,
    "buy_fused_threshold": 0.15,
    "sell_fused_threshold": -0.15,
    # Defaults tuned for safer / lower-drawdown behavior (see backtests).
    "use_proba_thresholds": True,
    "buy_proba_threshold": 0.2,
    "sell_proba_threshold": 0.45,
}


class ToggleResponse(BaseModel):
    automation: bool


class DecisionRequest(BaseModel):
    symbol: str
    interval: str = "1m"
    limit: int = 200
    sentiment_index: float = 0.0
    rules_weight: float = 0.45
    ml_weight: float = 0.55
    veto_threshold: float = -0.35
    buy_fused_threshold: float = 0.15
    sell_fused_threshold: float = -0.15
    use_proba_thresholds: bool = False
    buy_proba_threshold: float = 0.55
    sell_proba_threshold: float = 0.45


class AutomationStartRequest(BaseModel):
    symbol: str | None = Field(default=None, description="If omitted, uses the last symbol")
    interval: str = "1m"
    limit: int = 200
    qty: float = 1.0
    rules_weight: float = 0.45
    ml_weight: float = 0.55
    veto_threshold: float = -0.35
    tick_seconds: int = 30
    sentiment_lookback_minutes: int = 60
    stop_loss_bps: float = Field(default=250.0, ge=0.0, le=50_000.0)
    take_profit_bps: float = Field(default=400.0, ge=0.0, le=50_000.0)
    trailing_stop_bps: float = Field(default=0.0, ge=0.0, le=50_000.0)
    buy_fused_threshold: float = 0.15
    sell_fused_threshold: float = -0.15
    use_proba_thresholds: bool = False
    buy_proba_threshold: float = 0.55
    sell_proba_threshold: float = 0.45


async def _compute_sentiment_index(*, symbol: str, lookback_minutes: int) -> float:
    """
    Prototype sentiment for automation loop.
    Uses Reddit aggregation if credentials exist; otherwise defaults to 0.0.
    """
    now = datetime.now(timezone.utc)
    start = pd.Timestamp(now) - pd.Timedelta(minutes=lookback_minutes)
    end = pd.Timestamp(now)

    # Avoid blocking the event loop while Reddit API/network work happens.
    sent = await asyncio.to_thread(reddit_sentiment_features, symbols=[symbol], start=start, end=end)
    if sent.empty:
        return 0.0
    if float(sent["sent_count"].max()) <= 0:
        return 0.0
    return float(sent["sent_mean"].mean())


async def _automation_loop() -> None:
    global _automation_task
    try:
        while _state.get("automation"):
            sym = _automation_cfg.get("symbol")
            if not sym:
                await asyncio.sleep(5)
                continue

            entries = list_entries()
            active = next((e for e in entries if e.active), None) or (entries[0] if entries else None)
            if active is None:
                # No model yet; wait and retry.
                await asyncio.sleep(10)
                continue

            try:
                df = await fetch_klines(
                    KlineQuery(symbol=sym, interval=_automation_cfg["interval"], limit=_automation_cfg["limit"])
                )
                sentiment_index = await _compute_sentiment_index(
                    symbol=sym,
                    lookback_minutes=int(_automation_cfg["sentiment_lookback_minutes"]),
                )

                last_close = float(df["close"].iloc[-1])
                pos = _broker.get_position(sym)

                # Trailing stop needs memory of the highest price since entry.
                if "_peak_price" not in _automation_cfg:
                    _automation_cfg["_peak_price"] = {}  # type: ignore[assignment]
                peak_price_by_sym: dict[str, float] = _automation_cfg["_peak_price"]  # type: ignore[assignment]

                if float(pos.qty) > 0.0:
                    # Update peak price if we're long.
                    peak_price_by_sym[sym] = max(float(peak_price_by_sym.get(sym, pos.avg_price or last_close)), last_close)

                    # Risk overrides (aim: reduce maximum loss).
                    stop_loss_bps = float(_automation_cfg.get("stop_loss_bps", 0.0))
                    take_profit_bps = float(_automation_cfg.get("take_profit_bps", 0.0))
                    trailing_stop_bps = float(_automation_cfg.get("trailing_stop_bps", 0.0))

                    stop_price = pos.avg_price * (1.0 - stop_loss_bps / 10_000.0) if stop_loss_bps > 0.0 else None
                    tp_price = pos.avg_price * (1.0 + take_profit_bps / 10_000.0) if take_profit_bps > 0.0 else None
                    trail_price = peak_price_by_sym[sym] * (1.0 - trailing_stop_bps / 10_000.0) if trailing_stop_bps > 0.0 else None

                    forced_action: str | None = None
                    forced_reason: str | None = None
                    if stop_price is not None and last_close <= float(stop_price):
                        forced_action = "SELL"
                        forced_reason = "stop_loss"
                    elif tp_price is not None and last_close >= float(tp_price):
                        forced_action = "SELL"
                        forced_reason = "take_profit"
                    elif trail_price is not None and last_close <= float(trail_price):
                        forced_action = "SELL"
                        forced_reason = "trailing_stop"

                    if forced_action is not None:
                        trade = _broker.submit(
                            trade_id=f"auto_{uuid.uuid4().hex[:10]}",
                            symbol=sym,
                            side=forced_action,  # "SELL"
                            qty=float(pos.qty),
                            price=last_close,
                        )
                        record_alert(
                            alert_type="TRADE_SIM",
                            message=f"Automation {forced_action} {sym} (risk:{forced_reason}) price={last_close:.6f} pnl_delta={trade.realized_pnl_delta:.6f}",
                            meta={
                                "symbol": sym,
                                "action": forced_action,
                                "confidence": 0.0,
                                "reason": forced_reason,
                                "trade_realized_pnl_delta": trade.realized_pnl_delta,
                            },
                        )
                        # After forced SELL, skip model decision this tick.
                        continue
                else:
                    # Not in position: reset peak memory.
                    peak_price_by_sym[sym] = 0.0

                d = decide(
                    model_path=active.artifact_path,
                    ohlcv=pd.DataFrame(df),
                    sentiment_index=sentiment_index,
                    rules_weight=float(_automation_cfg["rules_weight"]),
                    ml_weight=float(_automation_cfg["ml_weight"]),
                    veto_threshold=float(_automation_cfg["veto_threshold"]),
                    buy_fused_threshold=float(_automation_cfg["buy_fused_threshold"]),
                    sell_fused_threshold=float(_automation_cfg["sell_fused_threshold"]),
                    use_proba_thresholds=bool(_automation_cfg.get("use_proba_thresholds", False)),
                    buy_proba_threshold=float(_automation_cfg.get("buy_proba_threshold", 0.55)),
                    sell_proba_threshold=float(_automation_cfg.get("sell_proba_threshold", 0.45)),
                )

                if (not d.vetoed) and d.action in ("BUY", "SELL"):
                    trade = _broker.submit(
                        trade_id=f"auto_{uuid.uuid4().hex[:10]}",
                        symbol=sym,
                        side=d.action,  # "BUY" | "SELL"
                        qty=float(_automation_cfg["qty"]),
                        price=last_close,
                    )
                    record_alert(
                        alert_type="TRADE_SIM",
                        message=f"Automation {d.action} {sym} qty={float(_automation_cfg['qty'])} price={last_close:.6f} pnl_delta={trade.realized_pnl_delta:.6f}",
                        meta={
                            "symbol": sym,
                            "action": d.action,
                            "confidence": d.confidence,
                            "reason": d.reason,
                            "trade_realized_pnl_delta": trade.realized_pnl_delta,
                        },
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                # Keep the loop alive if one tick fails.
                record_alert(
                    alert_type="SYSTEM",
                    message="Automation tick failed; will retry.",
                    meta={"symbol": _automation_cfg.get("symbol")},
                )

            tick = int(_automation_cfg.get("tick_seconds", 30))
            await asyncio.sleep(max(1, tick))
    finally:
        _automation_task = None


class DecisionResponse(BaseModel):
    as_of: datetime
    symbol: str
    model_id: str | None
    action: str
    confidence: float
    vetoed: bool
    reason: str


@router.post("/automation/start", response_model=ToggleResponse)
async def start(req: AutomationStartRequest):
    _automation_cfg.update(
        {
            "symbol": req.symbol if req.symbol is not None else _automation_cfg.get("symbol"),
            "interval": req.interval,
            "limit": req.limit,
            "qty": req.qty,
            "rules_weight": req.rules_weight,
            "ml_weight": req.ml_weight,
            "veto_threshold": req.veto_threshold,
            "tick_seconds": req.tick_seconds,
            "sentiment_lookback_minutes": req.sentiment_lookback_minutes,
            "stop_loss_bps": req.stop_loss_bps,
            "take_profit_bps": req.take_profit_bps,
            "trailing_stop_bps": req.trailing_stop_bps,
            "buy_fused_threshold": req.buy_fused_threshold,
            "sell_fused_threshold": req.sell_fused_threshold,
            "use_proba_thresholds": req.use_proba_thresholds,
            "buy_proba_threshold": req.buy_proba_threshold,
            "sell_proba_threshold": req.sell_proba_threshold,
        }
    )
    _state["automation"] = True
    record_alert(alert_type="SYSTEM", message="Automation started (paper trading).", meta={"symbol": _automation_cfg.get("symbol")})

    global _automation_task
    if _automation_task is None or _automation_task.done():
        _automation_task = asyncio.create_task(_automation_loop())
    return ToggleResponse(automation=True)


@router.post("/automation/stop", response_model=ToggleResponse)
async def stop():
    _state["automation"] = False
    record_alert(alert_type="SYSTEM", message="Automation stopped.", meta={"symbol": _automation_cfg.get("symbol")})

    global _automation_task
    if _automation_task is not None and not _automation_task.done():
        _automation_task.cancel()
        _automation_task = None
    return ToggleResponse(automation=False)


@router.get("/automation", response_model=ToggleResponse)
def automation_state():
    return ToggleResponse(automation=bool(_state["automation"]))


@router.post("/decision", response_model=DecisionResponse)
async def decision(req: DecisionRequest):
    # Pick active model (if any)
    entries = list_entries()
    active = next((e for e in entries if e.active), None)
    if active is None and entries:
        active = entries[0]

    df = await fetch_klines(KlineQuery(symbol=req.symbol, interval=req.interval, limit=req.limit))
    if active is None:
        return DecisionResponse(
            as_of=datetime.utcnow(),
            symbol=req.symbol,
            model_id=None,
            action="HOLD",
            confidence=0.0,
            vetoed=False,
            reason="no_model_loaded",
        )

    d = decide(
        model_path=active.artifact_path,
        ohlcv=pd.DataFrame(df),
        sentiment_index=req.sentiment_index,
        rules_weight=req.rules_weight,
        ml_weight=req.ml_weight,
        veto_threshold=req.veto_threshold,
        buy_fused_threshold=req.buy_fused_threshold,
        sell_fused_threshold=req.sell_fused_threshold,
        use_proba_thresholds=req.use_proba_thresholds,
        buy_proba_threshold=req.buy_proba_threshold,
        sell_proba_threshold=req.sell_proba_threshold,
    )
    return DecisionResponse(
        as_of=datetime.utcnow(),
        symbol=req.symbol,
        model_id=active.id,
        action=d.action,
        confidence=d.confidence,
        vetoed=d.vetoed,
        reason=d.reason,
    )

