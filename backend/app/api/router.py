from fastapi import APIRouter

from app.api.routes.coins import router as coins_router
from app.api.routes.ml import router as ml_router
from app.api.routes.market import router as market_router
from app.api.routes.paper import router as paper_router
from app.api.routes.sentiment import router as sentiment_router
from app.api.routes.trading import router as trading_router
from app.api.routes.alerts import router as alerts_router
from app.api.routes.backtest import router as backtest_router
from app.api.routes.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(coins_router, prefix="/coins", tags=["coins"])
api_router.include_router(ml_router, prefix="/ml", tags=["ml"])
api_router.include_router(market_router, prefix="/market", tags=["market"])
api_router.include_router(paper_router, prefix="/paper", tags=["paper"])
api_router.include_router(sentiment_router, prefix="/sentiment", tags=["sentiment"])
api_router.include_router(trading_router, prefix="/trading", tags=["trading"])
api_router.include_router(alerts_router, prefix="/alerts", tags=["alerts"])
api_router.include_router(backtest_router, prefix="/backtest", tags=["backtest"])
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

