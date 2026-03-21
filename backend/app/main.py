from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.db import Base, engine
from app import models  # noqa: F401


def create_app() -> FastAPI:
    app = FastAPI(title="CryptoVolt API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.on_event("startup")
    def _create_tables():
        Base.metadata.create_all(bind=engine)

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


app = create_app()

