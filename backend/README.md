# CryptoVolt backend

For full-stack setup (frontend, env vars, Docker), see the **[repo root `README.md`](../README.md)**.

## Run (Windows PowerShell)

```powershell
cd path\to\CryptoVolt\backend
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or from repo root: `.\scripts\run-backend-local.ps1`

Then open:
- API docs: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## Coin universe API (cheap + growing)

`GET /api/coins/recommended`

Example:

`/api/coins/recommended?limit=20&max_price=2&min_change_24h=3&min_quote_volume_24h=5000000`

## Train XGBoost (recommended universe)

PowerShell-safe (no JSON escaping pain):

```powershell
.\backend\.venv\Scripts\python -c "import httpx; payload={'universe':'recommended','limit':10,'max_price':2,'interval':'1m','limit_per_symbol':300,'tune':True,'tune_trials':8}; r=httpx.post('http://127.0.0.1:8000/api/ml/train/xgb', json=payload, timeout=60); print(r.status_code); print(r.text)"
```

Check job status:

```powershell
.\backend\.venv\Scripts\python -c "import httpx; job_id='PUT_JOB_ID_HERE'; r=httpx.get(f'http://127.0.0.1:8000/api/ml/jobs/{job_id}', timeout=30); print(r.status_code); print(r.text)"
```

