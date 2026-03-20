# CryptoVolt (Docker)

## Start everything
```powershell
docker compose up -d --build
```

Backend:
- `http://localhost:8000/docs`
- `http://localhost:8000/health`

Frontend:
- `http://localhost:5173`

## Daily retraining
Retraining is handled by the `trainer` container, which calls:
- `POST /api/ml/train/xgb`
- then polls `/api/ml/jobs/{job_id}`
- and activates the model via `POST /api/ml/models/activate`

### Optional environment variables (create an `.env` next to `docker-compose.yml`)
- `DISCORD_WEBHOOK_URL`
- `RUN_TRAINING_ON_START` (set to `1` to test immediately)
- `TRAIN_INTERVAL_SECONDS` (default `86400` = 1 day)
- `TRAIN_REQUEST_LIMIT` / `TRAIN_REQUEST_MAX_PRICE` / etc.

