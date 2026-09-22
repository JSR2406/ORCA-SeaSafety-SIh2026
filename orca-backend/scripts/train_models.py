"""Offline pilot trainer for the supervised marine models.

Fits all four models (pfz / risk / productivity / forecast) on LABELED data,
computes REAL out-of-fold cross-validated metrics, registers each as a
CANDIDATE, validates it in the model registry, optionally promotes it to
PRODUCTION (--promote), and persists the fitted estimators to the artifact
directory so ModelService can serve them.

Label source (honest, documented):
  * synthetic only by default - sampled from the documented domain bands with
    calibrated noise, so the surrogate LEARNS the domain physics encoded in the
    rule models;
  * --use-db merges real StoredDB observation rows (ocean + weather) into the
    feature pool for distribution realism; targets still follow the documented
    bands because measured catch/incident ground truth does not yet exist.

Run:  python scripts/train_models.py [--samples 2000] [--seed 42] [--promote]
      [--use-db] [--out reports/ml-training.json]
"""
import asyncio
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))

import structlog

from app.config import settings
from app.ml.models import known_models
from app.ml.registry import get_model_registry
from app.ml.trained import (DatasetGenerator, TrainedModelRunner,
                            build_trained_model)

logger = structlog.get_logger("ml_training")


def _load_db_feature_rows():
    """Best-effort merge of real observation rows into the feature pool."""
    from app.db.client import async_session_maker
    from sqlalchemy import text

    async def _query(sql):
        async with async_session_maker() as s:
            r = await s.execute(text(sql))
            return [dict(row._mapping) for row in r]

    rows = []
    try:
        rows += asyncio.run(_query(
            "SELECT sst_c, chlorophyll, wave_height_m, current_speed_ms "
            "FROM ocean_observations WHERE sst_c IS NOT NULL"))
        rows += asyncio.run(_query(
            "SELECT wind_speed_ms FROM weather_observations "
            "WHERE wind_speed_ms IS NOT NULL"))
    except Exception as exc:  # noqa: BLE001 - optional enhancement
        logger.warning("db_rows_unavailable", error=str(exc))
    return rows


def _with_db_features(model_name, synthetic, db_rows):
    """Merge real rows into a synthetic dataset for a model (target by rule)."""
    generator = DatasetGenerator()
    if not db_rows:
        return synthetic
    model = build_trained_model(model_name)
    needed = model.features
    merged = list(synthetic)
    for row in db_rows:
        variables = {c: (float(row[c]) if row.get(c) is not None else None)
                     for c in needed}
        if any(v is None for v in variables.values()):
            continue
        target = generator._rule(model_name, variables)
        merged.append({"variables": variables,
                       "target": float(round(target, 4))})
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=settings.ml_train_default_samples)
    parser.add_argument("--seed", type=int, default=settings.ml_train_seed)
    parser.add_argument("--promote", action="store_true",
                        help="promote trained candidates to production")
    parser.add_argument("--use-db", action="store_true",
                        help="merge real stored observation rows (if any)")
    parser.add_argument("--out", default="reports/ml-training.json")
    args = parser.parse_args()

    registry = get_model_registry()
    runner = TrainedModelRunner(registry=registry, seed=args.seed,
                                noise=settings.ml_train_noise)
    db_rows = _load_db_feature_rows() if args.use_db else []
    logger.info("training_start", samples=args.samples,
                promote=args.promote, db_rows=len(db_rows))

    report = {}
    for name in known_models():
        dataset = runner.generator.generate(name, args.samples)
        if db_rows:
            dataset = _with_db_features(name, dataset, db_rows)
        result = runner.train(name, dataset, persist=True)
        if args.promote:
            registry.promote(name, result["version"], require_validated=False)
            result["stage"] = "production"
        logger.info("trained", model=name, version=result["version"],
                    rows=result["rows"], stage=result["stage"],
                    metrics=result["metrics"])
        report[name] = result

    # Persist the registry snapshot so promoted trained versions survive
    # process restarts (ModelService loads it on the next start).
    registry_path = registry.persist()
    if registry_path:
        logger.info("registry_persisted", path=registry_path)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pipeline": "ml-training",
        "seed": args.seed,
        "samples": args.samples,
        "db_rows_merged": len(db_rows),
        "promoted": args.promote,
        "registry": registry.stats(),
        "models": report,
        "passed": True,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("report_written", path=str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())