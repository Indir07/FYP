# CryptoVolt — project overview

High-level map of the repo for onboarding and operations. **Do not commit secrets**; use `.env` at repo root (gitignored).

## Layout

| Path | Role |
|------|------|
| `backend/` | FastAPI app: auth, ML training/registry, market/sentiment, trading, backtest, alerts |
| `frontend/` | React + Vite + TypeScript: dashboard, models, backtesting, auth, alerts |
| `trainer/` | Optional scheduled job: calls `POST /api/ml/train/xgb`, polls job, activates model |
| `scripts/` | PowerShell helpers for local backend/frontend |
| `docker-compose.yml` | Postgres, backend, frontend, trainer |
| `.env` | Local secrets (SMTP, Reddit, Discord, `DATABASE_URL`, JWT, etc.) |

## Runtime flows

1. **Auth** — Signup/login with email OTP (`/api/auth/*`), JWT in `localStorage`, protected routes via `RequireAuth`.
2. **Dashboard** — Binance klines + sentiment score + hybrid trading decision + optional automation (paper).
3. **ML** — `train_xgb_multi`: paginated klines → features + Reddit/VADER (optional) → labels → XGBoost → `backend/_model_registry/` + metrics CSV in `_datasets/`.
4. **Inference** — `get_model_for_symbol()` prefers per-symbol model, else active global model.
5. **Alerts** — In-memory + optional Discord webhook.

## API surface (`/api/...`)

- `auth` — signup, login, OTP, password reset  
- `coins` — recommended / top-10 universe  
- `market` — klines  
- `sentiment` — Reddit + fallback proxy  
- `trading` — decision, automation start/stop  
- `ml` — train XGB, jobs, models, activate  
- `backtest` — run backtest  
- `alerts` — recent, test  

OpenAPI: `http://localhost:8000/docs`

## Environment variables (names only)

| Variable | Used for |
|----------|----------|
| `DATABASE_URL` | SQLAlchemy (Postgres in Docker; default local SQLite `backend/cryptovolt.db`) |
| `CRYPTOVOLT_MODEL_DIR` | Model registry path |
| `CRYPTOVOLT_DATA_DIR` | Training CSV output |
| `JWT_SECRET_KEY`, `JWT_EXPIRE_HOURS` | Auth tokens |
| `SMTP_*`, `FRONTEND_BASE_URL`, `AUTH_*` | Email OTP & password reset |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | Reddit training + live sentiment |
| `DISCORD_WEBHOOK_URL` | Alerts |
| `CORS_ORIGINS` | Comma-separated browser origins (optional). If unset, backend allows `localhost` / `127.0.0.1` on ports **5173–5176** (Vite often shifts when 5173 is taken). Set `FRONTEND_BASE_URL` to the same host/port for password-reset links. |

## Local vs Docker

- **Docker**: `docker compose` reads `.env` for substitution; backend `environment:` passes keys into the container.
- **Local uvicorn**: Loads **repo-root `.env`** via `python-dotenv` in `app/main.py` (install `python-dotenv` from `requirements.txt`).

## Frontend API base

Dev uses relative `/api` + Vite proxy (`vite.config.ts`). Optional `VITE_API_BASE_URL` for production builds.

## Further reading

- `README_DOCKER.md` — Docker & trainer  
- `TESTING_GUIDE.txt` — manual test checklist  
