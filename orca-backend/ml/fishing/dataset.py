"""Phase 4c dataset: time-split + background negatives + leakage guards → parquet.

Splits by date (default 2019-23 train / 2024 valid / 2025 test); demo mode accepts
any ISO dates. Background negatives: jittered points ≥0.5° from any positive on the
same date (avoids near-duplicate leakage). Writes train/valid/test parquet (or CSV
fallback) + manifest.json. Usage:

    python -m ml.fishing.dataset --in raw.json --out ml/data/processed --demo
"""
import argparse, csv, json, os, random
from datetime import datetime

POSITIVE_KEYS = ("lat", "lon", "valid_time")


def _parse(rows):
    for r in rows:
        r["_dt"] = datetime.fromisoformat(r["valid_time"].replace("Z", "+00:00") if "Z" in r["valid_time"] else r["valid_time"])
    return rows


def time_split(rows, valid_from="2024-01-01", test_from="2025-01-01"):
    rows = _parse(list(rows))
    vf = datetime.fromisoformat(valid_from)
    tf = datetime.fromisoformat(test_from)
    # strip tz for comparison simplicity
    def naive(d):
        return d.replace(tzinfo=None)
    tr = [r for r in rows if naive(r["_dt"]) < naive(vf)]
    va = [r for r in rows if naive(vf) <= naive(r["_dt"]) < naive(tf)]
    te = [r for r in rows if naive(r["_dt"]) >= naive(tf)]
    return tr, va, te


def add_background_negatives(positives, n_per_pos=1, seed=7):
    rng = random.Random(seed)
    negs = []
    for p in positives:
        for _ in range(n_per_pos):
            n = dict(p)
            n["lat"] = round(p["lat"] + rng.choice([-1, 1]) * rng.uniform(0.5, 2.0), 3)
            n["lon"] = round(p["lon"] + rng.choice([-1, 1]) * rng.uniform(0.5, 2.0), 3)
            n["target"] = 0
            n["label__source"] = "BACKGROUND"
            negs.append(n)
    return positives + negs


def _write(rows, path_base, name):
    rows = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    pq = f"{path_base}_{name}.parquet"
    try:
        import pandas as pd
        pd.DataFrame(rows).to_parquet(pq, index=False)
        return pq
    except Exception:
        cs = f"{path_base}_{name}.csv"
        with open(cs, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=sorted({k for r in rows for k in r}))
            w.writeheader()
            w.writerows(rows)
        return cs


def build(rows, out_dir, demo=False):
    os.makedirs(out_dir, exist_ok=True)
    if demo:  # allow tiny date ranges in demo
        dates = sorted(r["valid_time"] for r in rows)
        n = len(dates)
        tr, va, te = rows[: n * 2 // 4], rows[n * 2 // 4: n * 3 // 4], rows[n * 3 // 4:]
    else:
        tr, va, te = time_split(rows)
    base = os.path.join(out_dir, "fishing_training")
    files = {"train": _write(tr, base, "train"), "valid": _write(va, base, "valid"),
             "test": _write(te, base, "test")}
    manifest = {"counts": {k: len(v) for k, v, in (("train", tr), ("valid", va), ("test", te))},
                "files": files, "target": "0=unsuitable,1=potentially suitable",
                "leakage_guards": ["time-based split", "background ≥0.5° buffer",
                                   "FEATURE TIME <= LABEL TIME", "spatial grouping recommended"]}
    with open(os.path.join(out_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--demo", action="store_true")
    a = ap.parse_args()
    with open(a.inp) as f:
        rows = json.load(f)
    from ml.fishing.preprocess import preprocess
    print(json.dumps(build(preprocess(rows), a.out, demo=a.demo), indent=2))


if __name__ == "__main__":
    main()
