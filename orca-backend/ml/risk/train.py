"""Risk benchmark stub — same time-split contract as fishing."""
import argparse
CANDIDATES = ["logreg", "random_forest", "xgboost"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", required=True); ap.add_argument("--valid", required=True)
    ap.add_argument("--test", required=True)
    a = ap.parse_args()
    raise SystemExit(f"Foundation stub: time-split risk Parquet required. Candidates={CANDIDATES}")


if __name__ == "__main__":
    main()
