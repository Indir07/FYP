from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.binance_market import KlineQuery, fetch_klines
from app.trading.paper_broker_instance import broker as _broker
from app.services.alerts_service import record_alert

router = APIRouter()


class SubmitRequest(BaseModel):
    symbol: str
    side: str  # BUY/SELL
    qty: float = 1.0


@router.get("/state")
def state():
    return _broker.snapshot()


@router.post("/submit")
async def submit(req: SubmitRequest):
    df = await fetch_klines(KlineQuery(symbol=req.symbol, interval="1m", limit=2))
    price = float(df["close"].iloc[-1])
    t = _broker.submit(
        trade_id=f"pt_{uuid.uuid4().hex[:10]}",
        symbol=req.symbol,
        side="BUY" if req.side.upper() == "BUY" else "SELL",
        qty=float(req.qty),
        price=price,
    )
    record_alert(
        alert_type="TRADE_SIM",
        message=f"Paper {req.side.upper()} {req.symbol} qty={req.qty} price={price:.6f} pnl_delta={t.realized_pnl_delta:.6f}",
        meta={"symbol": req.symbol, "side": req.side.upper(), "qty": req.qty, "price": price, "pnl_delta": t.realized_pnl_delta},
    )
    return {"as_of": datetime.utcnow().isoformat(), "trade": t.__dict__, "state": _broker.snapshot()}

