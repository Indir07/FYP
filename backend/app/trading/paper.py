from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal


Side = Literal["BUY", "SELL"]


@dataclass
class Position:
    symbol: str
    qty: float = 0.0
    avg_price: float = 0.0
    realized_pnl: float = 0.0


@dataclass
class PaperTrade:
    id: str
    ts: str
    symbol: str
    side: Side
    qty: float
    price: float
    fee: float
    realized_pnl_delta: float


class PaperBroker:
    def __init__(self, fee_bps: float = 4.0):
        self.fee_bps = fee_bps
        self.positions: dict[str, Position] = {}
        self.trades: list[PaperTrade] = []

    def get_position(self, symbol: str) -> Position:
        return self.positions.get(symbol) or Position(symbol=symbol)

    def submit(self, *, trade_id: str, symbol: str, side: Side, qty: float, price: float) -> PaperTrade:
        pos = self.positions.get(symbol)
        if pos is None:
            pos = Position(symbol=symbol)
            self.positions[symbol] = pos

        fee = (self.fee_bps / 10_000.0) * abs(qty * price)
        realized_delta = 0.0

        if side == "BUY":
            # Increase long position (simple prototype: long-only averaging)
            new_qty = pos.qty + qty
            if new_qty > 0:
                pos.avg_price = ((pos.avg_price * pos.qty) + (price * qty)) / new_qty
            pos.qty = new_qty
        else:  # SELL
            sell_qty = min(qty, pos.qty)
            realized_delta = (price - pos.avg_price) * sell_qty - fee
            pos.realized_pnl += realized_delta
            pos.qty -= sell_qty
            if pos.qty <= 0:
                pos.qty = 0.0
                pos.avg_price = 0.0

        t = PaperTrade(
            id=trade_id,
            ts=datetime.utcnow().isoformat(),
            symbol=symbol,
            side=side,
            qty=qty,
            price=price,
            fee=fee,
            realized_pnl_delta=realized_delta,
        )
        self.trades.append(t)
        return t

    def snapshot(self) -> dict:
        return {
            "positions": {k: asdict(v) for k, v in self.positions.items()},
            "trades": [asdict(t) for t in self.trades[-200:]],
        }

