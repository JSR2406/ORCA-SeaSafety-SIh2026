"""Phase 7 dataset: risk rows with rule-derived demo labels.

Production labels should come from incident/advisory history (IMD warnings,
accident reports). Demo labels: 1 if wave>=2.5m or wind>=12m/s or cyclone<200km
or lightning==1 — a transparent, auditable rule, NOT a learned truth.
Time-split + parquet + manifest, same contract as fishing.
"""
import argparse, csv, json, os
from datetime import datetime


def demo_label(r):
    return 1 if (r.get("wave_height_m", 0) >= 2.5 or r.get("wind_speed_ms", 0) >= 12.0
                 or r.get("cyclone_distance_km", 9999) < 200
                 or r.get("lightning_flag", 0) == 1) else 0


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
            w.writeheader(); w.writerows(rows)
        return cs


def build(rows, out_dir, demo=False):
    os.makedirs(out_dir, exist_ok=True)
    for r in rows:
        r.setdefault("target", demo_label(r))
    if demo:
        n = len(rows)
        tr, va, te = rows[: n * 2 // 4], rows[n * 2 // 4: n * 3 // 4], rows[n * 3 // 4:]
    else:
        from ml.fishing.dataset import time_split
        tr, va, te = time_split(rows)
    base = os.path.join(out_dir, "risk_training")
    files = {"train": _write(tr, base, "train"), "valid": _write(va, base, "valid"),
             "test": _write(te, base, "test")}
    manifest = {"counts": {"train": len(tr), "valid": len(va), "test": len(te)},
                "files": files, "target": "0=low-risk,1=high-risk (demo rule; replace with incident history)",
                "leakage_guards": ["time-based split", "FEATURE TIME <= LABEL TIME"]}
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
        print(json.dumps(build(json.load(f), a.out, demo=a.demo), indent=2))


if __name__ == "__main__":
    main()
