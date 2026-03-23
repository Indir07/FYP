from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import joblib


MODEL_DIR = Path(os.getenv("CRYPTOVOLT_MODEL_DIR", "D:/CryptoVolt/backend/_model_registry"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)

# Prefer the biggest training run (10 symbols × 120k ≈ 1.2M rows before balancing).
_DESIRED_N_SAMPLES_DEFAULT = 1_200_000
DESIRED_N_SAMPLES = int(os.getenv("CRYPTOVOLT_DESIRED_N_SAMPLES", str(_DESIRED_N_SAMPLES_DEFAULT)))


@dataclass(frozen=True)
class ModelEntry:
    id: str
    kind: Literal["xgb_classifier"]
    created_at: str
    symbols: list[str]
    interval: str
    params: dict
    metrics: dict
    artifact_path: str
    active: bool


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_entry(*, kind: Literal["xgb_classifier"], symbols: list[str], interval: str, params: dict, metrics: dict):
    model_id = f"{kind}_{uuid.uuid4().hex[:12]}"
    artifact_path = str(MODEL_DIR / f"{model_id}.joblib")
    meta_path = str(MODEL_DIR / f"{model_id}.json")
    entry = ModelEntry(
        id=model_id,
        kind=kind,
        created_at=_now(),
        symbols=symbols,
        interval=interval,
        params=params,
        metrics=metrics,
        artifact_path=artifact_path,
        active=False,
    )
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(asdict(entry), f, indent=2)
    return entry, meta_path


def save_artifact(entry: ModelEntry, obj) -> None:
    joblib.dump(obj, entry.artifact_path)


def list_entries() -> list[ModelEntry]:
    out: list[ModelEntry] = []
    for p in sorted(MODEL_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        # `artifact_path` is persisted in JSON for convenience, but it can become stale
        # when the app is deployed in Docker (Windows absolute paths won't exist
        # inside the container). Re-anchor the artifact path to the current MODEL_DIR.
        model_id = d.get("id")
        if model_id:
            d["artifact_path"] = str(MODEL_DIR / f"{model_id}.joblib")
        out.append(ModelEntry(**d))
    return out


def set_active(model_id: str) -> ModelEntry | None:
    entries = list_entries()
    if not entries:
        return None

    desired_entries = [e for e in entries if int(e.metrics.get("n_samples", -1)) == DESIRED_N_SAMPLES]
    desired_ids = {e.id for e in desired_entries}

    # If caller tries to activate a non-desired model, keep the desired 1.2M model active instead.
    # (Non-destructive: we only flip the `active` flag, we do not delete files.)
    chosen_id = model_id
    if desired_entries and model_id not in desired_ids:
        chosen_id = desired_entries[0].id

    found = None
    for e in entries:
        meta = MODEL_DIR / f"{e.id}.json"
        if not meta.exists():
            continue
        updated = asdict(e)
        updated["active"] = e.id == chosen_id
        with open(meta, "w", encoding="utf-8") as f:
            json.dump(updated, f, indent=2)
        if e.id == chosen_id:
            found = ModelEntry(**updated)
    return found


def get_model_for_symbol(symbol: str, interval: str | None = None) -> ModelEntry | None:
    """
    Resolve model for execution.

    Order:
    1) Most recent model with `metrics.n_samples == 1_200_000` (optionally matching `interval`)
       - if a 1.2M model is symbol-specific, prefer it.
    2) Most recent symbol-specific model (single-symbol training run).
    3) Active global model.
    4) Most recent available model.
    """
    entries = list_entries()
    if not entries:
        return None

    symbol_upper = symbol.upper()

    # Prefer desired 1.2M training run.
    desired_entries = [e for e in entries if int(e.metrics.get("n_samples", -1)) == DESIRED_N_SAMPLES]
    if desired_entries:
        if interval:
            desired_interval = [e for e in desired_entries if e.interval == interval]
            if desired_interval:
                desired_entries = desired_interval
        # If any desired entry is explicitly marked active, prefer among those.
        # This keeps “Activate selected model” consistent with what gets used.
        active_desired = [e for e in desired_entries if bool(e.active)]
        candidate_pool = active_desired if active_desired else desired_entries

        desired_symbol_specific = [
            e
            for e in candidate_pool
            if len(e.symbols) == 1 and e.symbols[0].upper() == symbol_upper
        ]
        if desired_symbol_specific:
            return desired_symbol_specific[0]

        return candidate_pool[0]

    # Fallback: previous behavior.
    symbol_specific = [
        e for e in entries if len(e.symbols) == 1 and e.symbols[0].upper() == symbol_upper
    ]
    if symbol_specific:
        return symbol_specific[0]

    active = next((e for e in entries if e.active), None)
    if active is not None:
        return active
    return entries[0]

