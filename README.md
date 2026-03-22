# CryptoVolt

Hybrid AI-powered cryptocurrency trading prototype: FastAPI backend, React (Vite) dashboard, optional scheduled trainer, XGBoost + LSTM pipelines, paper trading, and **Discord + persisted alerts**.

## Prerequisites

- **Python 3.11+** (backend venv)
- **Node.js 20+** (frontend)
- **PostgreSQL** (optional; default local dev uses SQLite at `backend/cryptovolt.db`)

## Quick start (Windows PowerShell)

### 1. Environment

Copy the example env and edit secrets:

```powershell
Copy-Item .env.example .env
# edit .env — at minimum set DATABASE_URL for Postgres, or leave unset for SQLite
# JWT_SECRET_KEY — set a strong value for production
# DISCORD_WEBHOOK_URL — optional; enables Discord notifications for alerts
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or from repo root:

```powershell
.\scripts\run-backend-local.ps1
```

- API docs: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev -- --host
```

Or:

```powershell
.\scripts\run-frontend-local.ps1
```

Open the URL Vite prints (usually **<http://localhost:5173>**). The dev server proxies `/api` to the backend.

### 4. Run both (two terminals)

```powershell
.\scripts\run-local-all.ps1
```

### CORS

If the frontend runs on a different port (e.g. 5174), set in `.env`:

```env
CORS_ORIGINS=http://localhost:5174,http://127.0.0.1:5174
```

If unset, the backend allows typical Vite ports **5173–5180**.

## Project layout

| Path | Description |
|------|-------------|
| `backend/` | FastAPI app, ML registry, trading, alerts (DB-backed + Discord) |
| `frontend/` | React dashboard |
| `trainer/` | Optional scheduled training job |
| `scripts/` | PowerShell helpers for local dev |
| `docker-compose.yml` | Postgres + backend + frontend + trainer |
| `docs/` | Extra documentation |

## Docker

See **`README_DOCKER.md`** for `docker compose up` and trainer notes.

## Alerts

- **Database**: `alert_records` table (created on startup). Alerts survive restarts.
- **Discord**: set `DISCORD_WEBHOOK_URL` in `.env` to receive webhook messages.
- **UI**: `Alerts` page lists recent alerts; **Test Discord webhook** sends a test message.

## Further reading

- `docs/PROJECT_OVERVIEW.md` — architecture map  
- `TESTING_GUIDE.txt` — manual test checklist  
- `README_DOCKER.md` — containers  

## Disclaimer

Research software only — not financial advice. Use paper trading by default.
