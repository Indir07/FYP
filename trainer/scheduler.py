import os
import time
from typing import Any

import httpx


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, str(default)))


def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, str(default)))


API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
RUN_TRAINING_ON_START = _env_bool("RUN_TRAINING_ON_START", False)
TRAIN_INTERVAL_SECONDS = _env_int("TRAIN_INTERVAL_SECONDS", 86400)
POLL_SECONDS = _env_int("POLL_SECONDS", 10)
USE_ACTIVATION = _env_bool("USE_ACTIVATION", True)

TRAIN_UNIVERSE = os.getenv("TRAIN_REQUEST_UNIVERSE", "recommended")
TRAIN_LIMIT = _env_int("TRAIN_REQUEST_LIMIT", 10)
TRAIN_MAX_PRICE = _env_float("TRAIN_REQUEST_MAX_PRICE", 0.5)
TRAIN_MIN_CHANGE_24H = _env_float("TRAIN_REQUEST_MIN_CHANGE_24H", 3.0)
TRAIN_MIN_QUOTE_VOLUME_24H = _env_float("TRAIN_REQUEST_MIN_QUOTE_VOLUME_24H", 5_000_000.0)
TRAIN_INTERVAL = os.getenv("TRAIN_REQUEST_INTERVAL", "1m")
TRAIN_LIMIT_PER_SYMBOL = _env_int("TRAIN_REQUEST_LIMIT_PER_SYMBOL", 120_000)
TRAIN_TUNE = _env_bool("TRAIN_REQUEST_TUNE", False)
TRAIN_TUNE_TRIALS = _env_int("TRAIN_REQUEST_TUNE_TRIALS", 40)
TRAIN_OPTIMIZE_METRIC = os.getenv("TRAIN_REQUEST_OPTIMIZE_METRIC", "roc_auc")
TRAIN_BALANCE_PER_CLASS = _env_int("TRAIN_REQUEST_BALANCE_PER_CLASS", 600_000)
TRAIN_SENTIMENT_POST_LIMIT = _env_int("TRAIN_REQUEST_SENTIMENT_POST_LIMIT", 150)


def _train_payload() -> dict[str, Any]:
    return {
        "universe": TRAIN_UNIVERSE,
        "symbols": [],
        "limit": TRAIN_LIMIT,
        "max_price": TRAIN_MAX_PRICE,
        "min_change_24h": TRAIN_MIN_CHANGE_24H,
        "min_quote_volume_24h": TRAIN_MIN_QUOTE_VOLUME_24H,
        "interval": TRAIN_INTERVAL,
        "limit_per_symbol": TRAIN_LIMIT_PER_SYMBOL,
        "tune": TRAIN_TUNE,
        "tune_trials": TRAIN_TUNE_TRIALS,
        "optimize_metric": TRAIN_OPTIMIZE_METRIC,
        "sentiment_post_limit": TRAIN_SENTIMENT_POST_LIMIT,
        "balance_classes": True,
        "balance_per_class": TRAIN_BALANCE_PER_CLASS,
    }


def _wait_for_job(client: httpx.Client, job_id: str) -> dict[str, Any]:
    while True:
        r = client.get(f"{API_BASE_URL}/api/ml/jobs/{job_id}", timeout=60)
        r.raise_for_status()
        j = r.json()
        status = j.get("status")
        if status in ("succeeded", "failed"):
            return j
        time.sleep(POLL_SECONDS)


def _activate_model(client: httpx.Client, model_id: str) -> None:
    r = client.post(
        f"{API_BASE_URL}/api/ml/models/activate",
        json={"model_id": model_id},
        timeout=60,
    )
    r.raise_for_status()


def _train_once() -> None:
    payload = _train_payload()
    with httpx.Client(timeout=300) as client:
        resp = client.post(f"{API_BASE_URL}/api/ml/train/xgb", json=payload, timeout=300)
        resp.raise_for_status()
        j = resp.json()
        job_id = j["job_id"]
        print(f"[trainer] started job_id={job_id}")

        result = _wait_for_job(client, job_id)
        status = result.get("status")
        print(f"[trainer] job finished status={status}")

        if status == "succeeded" and USE_ACTIVATION:
            model_id = result.get("model_id")
            if model_id:
                print(f"[trainer] activating model_id={model_id}")
                _activate_model(client, model_id=model_id)
                print("[trainer] activated")


if __name__ == "__main__":
    # Optional immediate training so the user can validate the pipeline.
    if RUN_TRAINING_ON_START:
        _train_once()

    while True:
        print(f"[trainer] sleeping {TRAIN_INTERVAL_SECONDS}s until next retrain")
        time.sleep(TRAIN_INTERVAL_SECONDS)
        _train_once()

