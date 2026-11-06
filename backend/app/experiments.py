"""Controlled distribution-shift experiments: detection vs. measured performance loss.

For every shift type and magnitude we draw repeated bootstrap batches from the held-out test set,
apply the shift, then record (a) what each detector flagged and (b) how model performance changed.
Cross-tabulating the two gives detection recall, false-alarm rate and missed shifts.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .metrics import compute_metrics
from .monitoring import MonitorConfig, ShiftMonitor
from .preprocessing import coerce_frame
from .utils import to_builtin

log = logging.getLogger(__name__)
DETECTORS = ["psi_moderate", "psi_major", "statistical", "missingness", "combined"]


def _continuous(reference, importance):
    return [c for c in importance if reference[c]["kind"] == "continuous"]


def make_shifts(reference: dict, importance: dict[str, float]) -> dict:
    cont = _continuous(reference, importance)
    cats = [c for c in importance if reference[c]["kind"] in ("discrete", "categorical")]
    shifts: dict = {}

    def std(c):
        return max(reference[c]["std"], 1e-9)

    if cont:
        top = cont[0]

        def mean_top(X, y, m, rng):
            X = X.copy(); X[top] = X[top] + m * std(top); return X, y

        def scale_top(X, y, m, rng):
            X = X.copy(); mu = reference[top]["mean"]; X[top] = mu + (X[top] - mu) * (1 + m); return X, y

        def mean_all(X, y, m, rng):
            X = X.copy()
            for c in cont:
                X[c] = X[c] + m * std(c)
            return X, y

        def noise_all(X, y, m, rng):
            X = X.copy()
            for c in cont:
                X[c] = X[c] + rng.normal(0, m * std(c), len(X))
            return X, y

        def missing_top(X, y, m, rng):
            X = X.copy(); X.loc[rng.random(len(X)) < m, top] = np.nan; return X, y

        def selection_top(X, y, m, rng):
            z = ((X[top] - reference[top]["mean"]) / std(top)).fillna(0).to_numpy()
            w = np.exp(np.clip(m * z, -30, 30)); w /= w.sum()
            idx = rng.choice(len(X), size=len(X), p=w)
            return X.iloc[idx].reset_index(drop=True), y[idx]

        shifts["mean_shift_top_feature"] = (mean_top, [0.25, 0.5, 1.0, 2.0])
        shifts["scale_shift_top_feature"] = (scale_top, [0.25, 0.5, 1.0, 2.0])
        shifts["mean_shift_all_continuous"] = (mean_all, [0.1, 0.25, 0.5, 1.0])
        shifts["noise_all_continuous"] = (noise_all, [0.1, 0.25, 0.5, 1.0])
        shifts["missing_top_feature"] = (missing_top, [0.05, 0.10, 0.25, 0.50])
        shifts["selection_shift_top_feature"] = (selection_top, [0.5, 1.0, 2.0])

    if cats:
        cat = cats[0]
        counts = reference[cat]["counts"]
        rare = min(counts, key=counts.get)

        def category_prior(X, y, m, rng):
            if reference[cat]["kind"] == "discrete":
                is_rare = (X[cat].map(lambda v: format(float(v), "g") if pd.notna(v) else None) == rare).to_numpy()
            else:
                is_rare = (X[cat] == rare).to_numpy()
            w = np.where(is_rare, 1 + 4 * m, 1.0); w = w / w.sum()
            idx = rng.choice(len(X), size=len(X), p=w)
            return X.iloc[idx].reset_index(drop=True), y[idx]

        shifts["category_prior_shift"] = (category_prior, [0.5, 1.0, 2.0])

    def prevalence(X, y, m, rng):
        base = y.mean()
        odds = base / (1 - base) * m
        target = odds / (1 + odds)
        pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
        n_pos = int(round(target * len(y)))
        idx = np.concatenate([rng.choice(pos, n_pos), rng.choice(neg, len(y) - n_pos)])
        rng.shuffle(idx)
        return X.iloc[idx].reset_index(drop=True), y[idx]

    shifts["label_prevalence_shift"] = (prevalence, [0.5, 2.0, 4.0])
    return shifts


def _confusion(df: pd.DataFrame, detector: str, truth_col: str = "shift_present") -> dict:
    """Evaluate a detector against a declared ground-truth label.

    Shift detection is the primary firewall task; performance degradation is a separate
    downstream outcome and must not be used as the ground truth for whether a shift existed.
    """
    flag, truth = df[detector].astype(bool), df[truth_col].astype(bool)
    tp, fp = int((flag & truth).sum()), int((flag & ~truth).sum())
    fn, tn = int((~flag & truth).sum()), int((~flag & ~truth).sum())
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_alarm_rate": fp / (fp + tn) if fp + tn else None}


def run_experiments(artifact_dir, repeats: int = 20, seed: int = 42, auc_drop: float = 0.03,
                    brier_increase: float = 0.02, recall_drop: float = 0.10,
                    config: MonitorConfig | None = None) -> dict:
    artifact_dir = Path(artifact_dir)
    art = joblib.load(artifact_dir / "cvd_model.joblib")
    holdout = pd.read_csv(artifact_dir / "holdout.csv", na_values=["?", "NA", "N/A", "null", "None", ""])
    target = art["target"]
    y = holdout[target].to_numpy().astype(int)
    X, _ = coerce_frame(holdout[art["features"]], art["feature_types"])
    thr, model, base = art["threshold"], art["model"], art["evaluation"]["test"]
    monitor = ShiftMonitor(art["reference"], config or MonitorConfig())
    rng = np.random.default_rng(seed)
    shifts = make_shifts(art["reference"], art["feature_importance"])
    plan = [("control", None, 0.0)] + [(n, f, m) for n, (f, mags) in shifts.items() for m in mags]

    rows = []
    for name, fn, mag in plan:
        for rep in range(repeats if name != "control" else repeats * 3):
            idx = rng.integers(0, len(X), len(X))
            Xb, yb = X.iloc[idx].reset_index(drop=True), y[idx]
            if fn is not None:
                Xb, yb = fn(Xb, yb, mag, rng)
            met = compute_metrics(yb, model.predict_proba(Xb)[:, 1], thr)
            rep_ = monitor.compare(Xb)
            det = rep_["detectors"]
            drops = {"auc": base["roc_auc"] - met["roc_auc"],
                     "brier": met["brier"] - base["brier"],
                     "recall": base["recall"] - met["recall"]}
            degraded = bool((not np.isnan(drops["auc"]) and drops["auc"] >= auc_drop)
                            or drops["brier"] >= brier_increase or drops["recall"] >= recall_drop)
            rows.append({"shift": name, "magnitude": mag, "rep": rep,
                         "shift_present": bool(name != "control"),
                         **{f"m_{k}": v for k, v in met.items()},
                         "auc_drop": drops["auc"], "brier_increase": drops["brier"],
                         "recall_drop": drops["recall"], "degraded": degraded,
                         "psi_moderate": det["psi_moderate"], "psi_major": det["psi_major"],
                         "statistical": det["statistical"], "missingness": det["missingness"],
                         "combined": rep_["status"] != "NO_SHIFT_DETECTED",
                         "max_psi": max((r["psi"] or 0) for r in rep_["results"])})
        log.info("finished %s (magnitude %s)", name, mag)

    trials = pd.DataFrame(rows)
    cells = trials.groupby(["shift", "magnitude"], sort=False).agg(
        n_trials=("rep", "size"), shift_present_rate=("shift_present", "mean"),
        mean_auc=("m_roc_auc", "mean"), mean_brier=("m_brier", "mean"),
        mean_recall=("m_recall", "mean"), mean_precision=("m_precision", "mean"),
        mean_auc_drop=("auc_drop", "mean"), mean_brier_increase=("brier_increase", "mean"),
        degraded_rate=("degraded", "mean"), mean_max_psi=("max_psi", "mean"),
        **{f"{d}_rate": (d, "mean") for d in DETECTORS}).reset_index()

    summary = {"baseline_test": base, "repeats": repeats, "seed": seed,
               "degradation_rule": {"auc_drop": auc_drop, "brier_increase": brier_increase,
                                    "recall_drop": recall_drop},
               "monitor_config": vars(monitor.config) if not hasattr(monitor.config, "__dataclass_fields__")
               else {f: getattr(monitor.config, f) for f in monitor.config.__dataclass_fields__},
               "control_false_degradation_rate": float(trials[trials["shift"] == "control"]["degraded"].mean()),
               "control_false_alert_rates": {
                   d: float(trials.loc[trials["shift"] == "control", d].mean()) for d in DETECTORS},
               "detector_confusion_overall": {d: _confusion(trials, d, "shift_present") for d in DETECTORS},
               "detector_confusion_performance_loss": {d: _confusion(trials, d, "degraded") for d in DETECTORS},
               "detector_confusion_by_shift": {
                   s: {d: _confusion(g, d, "degraded") for d in DETECTORS}
                   for s, g in trials[trials["shift"] != "control"].groupby("shift")},
               "notes": ["Primary detector confusion metrics use shift_present as ground truth: a shift is present when a synthetic perturbation was applied.",
                         "Performance degradation is measured separately using the AUC/Brier/recall rules; a detected shift need not cause measurable performance loss.",
                         "Control batches are unshifted bootstraps and estimate false alerts for shift detection.",
                         "Results are controlled-shift simulations on one dataset, not evidence of real-hospital reliability."]}
    trials.to_csv(artifact_dir / "experiment_trials.csv", index=False)
    cells.to_csv(artifact_dir / "experiment_results.csv", index=False)
    (artifact_dir / "experiment_summary.json").write_text(json.dumps(to_builtin(summary), indent=2))
    return to_builtin(summary)
