"""Command line: demo-data | train | validate | experiments."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BASE_DIR, get_settings


def make_demo_data(path: Path, n: int = 3000, seed: int = 0) -> None:
    """Synthetic heart-like data so the pipeline can be smoke-tested. NOT real patients."""
    rng = np.random.default_rng(seed)
    age = rng.normal(54, 9, n).clip(29, 80).round()
    sex = rng.integers(0, 2, n)
    chol = rng.normal(240, 50, n).clip(120, 560).round()
    bp = rng.normal(131, 17, n).clip(90, 200).round()
    hr = rng.normal(150, 22, n).clip(70, 202).round()
    bmi = rng.normal(27, 4.5, n).clip(16, 50).round(1)
    smoker = rng.choice(["never", "former", "current"], n, p=[0.5, 0.3, 0.2])
    cp = rng.integers(0, 4, n)
    logit = (0.05 * (age - 54) + 0.6 * sex + 0.008 * (chol - 240) + 0.02 * (bp - 131)
             - 0.02 * (hr - 150) + 0.5 * (smoker == "current") + 0.4 * (cp == 3) - 0.6)
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    df = pd.DataFrame({"patient_id": np.arange(n), "age": age, "sex": sex, "chest_pain_type": cp,
                       "resting_bp": bp, "cholesterol": chol, "max_heart_rate": hr, "bmi": bmi,
                       "smoking_status": smoker, "target": y})
    df.loc[rng.random(n) < 0.03, "cholesterol"] = np.nan
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("demo-data"); d.add_argument("--out", default=str(BASE_DIR / "data" / "demo.csv"))
    t = sub.add_parser("train")
    t.add_argument("--csv", required=True); t.add_argument("--target", required=True)
    t.add_argument("--id-columns", nargs="*", default=[]); t.add_argument("--positive-label")
    t.add_argument("--threshold-strategy", choices=["f1", "youden", "recall90"], default="f1")
    t.add_argument("--allow-suspicious", action="store_true"); t.add_argument("--drop-columns", nargs="*", default=[]); t.add_argument("--profile", default="custom"); t.add_argument("--seed", type=int, default=42)
    v = sub.add_parser("validate", help="test whether the dataset has learnable signal (run after train)")
    v.add_argument("--csv", required=True); v.add_argument("--target", required=True)
    v.add_argument("--id-columns", nargs="*", default=[]); v.add_argument("--positive-label")
    v.add_argument("--permutations", type=int, default=200)
    e = sub.add_parser("experiments")
    e.add_argument("--repeats", type=int, default=20); e.add_argument("--seed", type=int, default=42)
    r = sub.add_parser("regional-audit", help="compare held-out regional groups with the pooled training reference")
    r.add_argument("--region-column", default="State_Name")
    r.add_argument("--min-region-rows", type=int, default=30)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    if args.cmd == "demo-data":
        make_demo_data(Path(args.out)); print(f"Wrote synthetic demo data to {args.out}")
    elif args.cmd == "train":
        from .training import train
        meta = train(args.csv, args.target, args.id_columns, args.positive_label, settings.artifact_dir,
                     args.seed, threshold_strategy=args.threshold_strategy,
                     allow_suspicious=args.allow_suspicious, drop_columns=args.drop_columns, profile=args.profile)
        print(json.dumps({k: meta[k] for k in ("selected_model", "threshold", "evaluation", "audit")}, indent=2))
    elif args.cmd == "validate":
        import joblib
        from .validate import validate
        art = joblib.load(settings.artifact_path)
        hold = pd.read_csv(settings.artifact_dir / "holdout.csv")
        proba = art["model"].predict_proba(hold[art["features"]])[:, 1]
        rep = validate(args.csv, args.target, args.id_columns, args.positive_label, settings.artifact_dir,
                       holdout_proba=proba, holdout_y=hold[art["target"]].to_numpy(), n_perm=args.permutations)
        print(json.dumps({k: rep[k] for k in ("verdict", "verdict_explained", "cross_validated_auc_3x5",
                                              "permutation_test", "holdout_auc", "holdout_auc_95ci",
                                              "features_significant_after_bonferroni")}, indent=2))
        print(f"Full report: {settings.artifact_dir / 'validation_report.md'}")
    elif args.cmd == "regional-audit":
        from .regional_audit import run_regional_audit
        result = run_regional_audit(settings.artifact_dir, args.region_column, args.min_region_rows,
                                    config=settings.monitor)
        print(json.dumps(result["summary"], indent=2))
        print(f"Full report: {settings.artifact_dir / 'regional_shift_audit.md'}")
    else:
        from .experiments import run_experiments
        s = run_experiments(settings.artifact_dir, args.repeats, args.seed, settings.auc_drop_threshold,
                            settings.brier_increase_threshold, config=settings.monitor)
        print(json.dumps({"control_false_degradation_rate": s["control_false_degradation_rate"],
                          "detector_confusion_overall": s["detector_confusion_overall"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
