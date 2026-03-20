from __future__ import annotations

from app.trading.paper import PaperBroker

# Shared in-memory broker instance used by both:
# - paper trading API routes (for UI/state)
# - backend automation loop (so automated orders update the same state)
broker = PaperBroker()

