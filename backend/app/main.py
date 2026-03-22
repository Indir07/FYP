import os
from contextlib import asynccontextmanager
from pathlib import Path

# Repo-root `.env` (d:\CryptoVolt\.env) — loaded for local `uvicorn` runs.
# Docker Compose injects env vars directly; this still runs safely if dotenv missing.
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(_env_path)
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text

from app.api.router import api_router
from app.db import Base, DATABASE_URL, engine
from app import models  # noqa: F401


def _cors_origins() -> list[str]:
    """
    Allowed browser origins for credentialed API calls.
    If CORS_ORIGINS is unset, allow typical Vite dev ports (5173 is default; 5174+ when busy).
    Override with a comma-separated list in .env, e.g. CORS_ORIGINS=http://localhost:5174
    """
    raw = os.getenv("CORS_ORIGINS")
    if raw:
        return [o.strip() for o in raw.split(",") if o.strip()]
    hosts = ("http://localhost", "http://127.0.0.1")
    ports = (5173, 5174, 5175, 5176)
    return [f"{h}:{p}" for h in hosts for p in ports]


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        Base.metadata.create_all(bind=engine)
        yield

    app = FastAPI(title="CryptoVolt API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api")

    @app.get("/", response_class=HTMLResponse)
    def root_page():
        """
        Browser-friendly landing: opening http://localhost:8000/ should not look 'broken'.
        The operator UI is the Vite app (e.g. :5173); this is the API only.
        """
        return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"/><title>CryptoVolt API</title>
<style>body{font-family:system-ui,sans-serif;max-width:42rem;margin:2rem;line-height:1.5}
code{background:#f4f4f4;padding:2px 6px;border-radius:4px}</style></head>
<body>
<h1>CryptoVolt API</h1>
<p>Backend is <strong>running</strong>. This port serves JSON APIs, not the trading dashboard.</p>
<ul>
<li><a href="/docs">Swagger UI</a> — try endpoints here</li>
<li><a href="/health">Health check</a> — includes DB ping (<code>database</code>, <code>connected</code>)</li>
<li><a href="/openapi.json">OpenAPI JSON</a></li>
</ul>
<p><strong>Dashboard UI:</strong> run the frontend (<code>npm run dev</code> in <code>frontend/</code>), then open the URL Vite prints (often <code>http://localhost:5173</code>).</p>
</body></html>"""

    @app.get("/health")
    def health():
        """API liveness + database connectivity (uses DATABASE_URL from `.env`)."""
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={
                    "ok": False,
                    "database": "disconnected",
                    "detail": str(e),
                },
            )
        backend = (
            "postgresql"
            if DATABASE_URL.startswith("postgresql")
            else "sqlite"
        )
        return {"ok": True, "database": backend, "connected": True}

    return app


app = create_app()

