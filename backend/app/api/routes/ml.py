from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter
from fastapi import BackgroundTasks
from pydantic import BaseModel, Field

from app.ml.registry import create_entry, list_entries, save_artifact, set_active
from app.ml.train_xgb import train_xgb_multi
from app.services.binance_coins import get_recommended_universe, get_top10_famous_growing_universe

router = APIRouter()

_jobs: dict[str, dict] = {}


class TrainRequest(BaseModel):
  universe: Literal["recommended", "top10_famous_growing", "custom"] = "top10_famous_growing"
  symbols: list[str] = Field(default_factory=list)
  limit: int = 20
  max_price: float = 2.0
  min_change_24h: float = 3.0
  min_quote_volume_24h: float = 5_000_000.0
  interval: Literal["1m", "5m", "15m", "1h"] = "1m"
  limit_per_symbol: int = 750
  tune: bool = False
  tune_trials: int = 25
  optimize_metric: Literal["roc_auc", "accuracy", "f1", "profit", "sharpe"] = "roc_auc"
  # Controls how the y-label is defined: y=1 if future return > label_threshold.
  # Increasing label_threshold and/or label_horizon makes the task easier
  # (higher accuracy is possible) but changes what “BUY” corresponds to.
  label_horizon: int = 1
  label_threshold: float = 0.0
  label_method: Literal["simple", "vol_cost", "triple_barrier"] = "vol_cost"
  label_cost_bps: float = 4.0
  label_vol_mult: float = 0.35
  label_pt_sl_mult: float = 1.2
  # Strong-data training knobs.
  sentiment_post_limit: int = 200
  sentiment_required: bool = False
  min_sentiment_coverage: float = 0.02


class TrainStartResponse(BaseModel):
  job_id: str
  status: Literal["queued"]


class JobStatusResponse(BaseModel):
  job_id: str
  status: Literal["queued", "running", "succeeded", "failed"]
  started_at: datetime | None = None
  ended_at: datetime | None = None
  error: str | None = None
  model_id: str | None = None
  metrics: dict | None = None


class ModelListResponse(BaseModel):
  models: list[dict]


@router.post("/train/xgb", response_model=TrainStartResponse)
async def start_train_xgb(req: TrainRequest, bg: BackgroundTasks):
  job_id = f"job_{uuid.uuid4().hex[:12]}"
  _jobs[job_id] = {"status": "queued", "started_at": None, "ended_at": None, "error": None}

  async def run():
    _jobs[job_id]["status"] = "running"
    _jobs[job_id]["started_at"] = datetime.utcnow()
    try:
      if req.universe == "recommended":
        coins = await get_recommended_universe(
          limit=req.limit,
          max_price=req.max_price,
          min_change_24h=req.min_change_24h,
          min_quote_volume_24h=req.min_quote_volume_24h,
        )
        symbols = [c.symbol for c in coins]
      elif req.universe == "top10_famous_growing":
        coins = await get_top10_famous_growing_universe(limit=min(req.limit, 10))
        symbols = [c.symbol for c in coins]
      else:
        symbols = req.symbols

      result = await train_xgb_multi(
        symbols=symbols,
        interval=req.interval,
        limit_per_symbol=req.limit_per_symbol,
        tune=req.tune,
        tune_trials=req.tune_trials,
        optimize_metric=req.optimize_metric,
        label_horizon=req.label_horizon,
        label_threshold=req.label_threshold,
        label_method=req.label_method,
        label_cost_bps=req.label_cost_bps,
        label_vol_mult=req.label_vol_mult,
        label_pt_sl_mult=req.label_pt_sl_mult,
        sentiment_post_limit=req.sentiment_post_limit,
        sentiment_required=req.sentiment_required,
        min_sentiment_coverage=req.min_sentiment_coverage,
      )

      entry, _meta_path = create_entry(
        kind="xgb_classifier",
        symbols=result.symbols,
        interval=result.interval,
        params=result.params,
        metrics=result.metrics,
      )
      save_artifact(entry, result.model)
      # UC-06: When a training run finishes, automatically activate the newly
      # trained model so the UI trading/backtesting endpoints use it.
      # (The periodic `trainer` container also activates on its own, but this
      # keeps the UX correct when training is started from the operator UI.)
      set_active(entry.id)

      _jobs[job_id]["status"] = "succeeded"
      _jobs[job_id]["ended_at"] = datetime.utcnow()
      _jobs[job_id]["model_id"] = entry.id
      _jobs[job_id]["metrics"] = entry.metrics
    except Exception as e:
      _jobs[job_id]["status"] = "failed"
      _jobs[job_id]["ended_at"] = datetime.utcnow()
      _jobs[job_id]["error"] = str(e)

  # BackgroundTasks expects sync callable; wrap with asyncio.run
  def runner():
    import asyncio as _asyncio

    _asyncio.run(run())

  bg.add_task(runner)
  return TrainStartResponse(job_id=job_id, status="queued")


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
  j = _jobs.get(job_id)
  if not j:
    return JobStatusResponse(job_id=job_id, status="failed", error="Unknown job_id")
  return JobStatusResponse(job_id=job_id, **j)


@router.get("/models", response_model=ModelListResponse)
def models():
  return ModelListResponse(models=[m.__dict__ for m in list_entries()])


class ActivateRequest(BaseModel):
  model_id: str


@router.post("/models/activate")
def activate(req: ActivateRequest):
  m = set_active(req.model_id)
  return {"active": m.__dict__ if m else None}

