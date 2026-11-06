"""Dataset validation: is there any learnable signal in this data at all?

Run after training (`python -m app.cli validate --csv ... --target ... --id-columns ...`). Produces
`artifacts/validation_report.json` and `artifacts/validation_report.md`.

Why this exists: the shift-detection experiments only mean something if the model has real predictive
performance to lose. This module answers that with a label-permutation test (the null distribution of
cross-validated AUC when labels carry no information), bootstrap confidence intervals on the held-out
AUC, and per-feature univariate tests with a multiple-comparison correction.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold, cross_val_score, StratifiedKFold
from sklearn.pipeline import Pipeline

from .preprocessing import build_preprocessor, coerce_frame, infer_feature_types
from .training import NA_TOKENS, encode_target
from .utils import to_builtin


def _load(csv_path, target, id_columns, positive_label):
    data = pd.read_csv(csv_path, na_values=NA_TOKENS, skipinitialspace=True)
    data.columns = data.columns.astype(str).str.strip()
    data = data.dropna(subset=[target]).drop_duplicates().reset_index(drop=True)
    y = encode_target(data[target], positive_label)
    X = data.drop(columns=[target, *[c for c in id_columns if c in data.columns]])
    X = X.loc[:, X.nunique(dropna=True) > 1]
    types = infer_feature_types(X)
    X, _ = coerce_frame(X, types)
    return X, y, types


def bootstrap_auc_ci(y, p, n_boot: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    aucs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) == 2:
            aucs.append(roc_auc_score(y[idx], p[idx]))
    return float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))


def permutation_test(X, y, types, n_perm: int = 200, seed: int = 0) -> dict:
    """Null distribution of 5-fold CV AUC (logistic regression) under shuffled labels."""
    cv = StratifiedKFold(5, shuffle=True, random_state=seed)

    def score(labels):
        pipe = Pipeline([("pre", build_preprocessor(types)), ("clf", LogisticRegression(max_iter=3000))])
        return float(cross_val_score(pipe, X, labels, cv=cv, scoring="roc_auc").mean())

    observed = score(y)
    rng = np.random.default_rng(seed)
    null = np.array([score(pd.Series(rng.permutation(y.to_numpy()), index=y.index)) for _ in range(n_perm)])
    p_value = float((1 + (null >= observed).sum()) / (1 + n_perm))
    return {"observed_cv_auc": observed, "null_mean": float(null.mean()),
            "null_95th_percentile": float(np.percentile(null, 95)), "n_permutations": n_perm,
            "p_value": p_value}


def univariate_table(X, y, types) -> list[dict]:
    rows = []
    for col in X.columns:
        if types[col] != "numeric":
            continue
        s = X[col]
        mask = s.notna()
        a, b = s[mask & (y == 1)], s[mask & (y == 0)]
        auc = float(roc_auc_score(y[mask], s[mask]))
        p = float(mannwhitneyu(a, b, alternative="two-sided").pvalue)
        rows.append({"feature": col, "auc": auc, "p_value": p})
    m = len(rows)
    for r in rows:
        r["p_bonferroni"] = min(1.0, r["p_value"] * m)
        r["significant_after_correction"] = r["p_bonferroni"] < 0.05
    return sorted(rows, key=lambda r: r["p_value"])


def validate(csv_path, target, id_columns=(), positive_label=None, out_dir=None, holdout_proba=None,
             holdout_y=None, n_perm: int = 200, seed: int = 0) -> dict:
    out_dir = Path(out_dir) if out_dir else None
    X, y, types = _load(csv_path, target, id_columns, positive_label)

    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=seed)
    models = {
        "logistic_regression": LogisticRegression(max_iter=3000),
        "random_forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=3, n_jobs=-1, random_state=seed),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=150, learning_rate=0.05, random_state=seed),
    }
    cv_auc = {}
    for name, est in models.items():
        pipe = Pipeline([("pre", build_preprocessor(types)), ("clf", est)])
        s = cross_val_score(pipe, X, y, cv=cv, scoring="roc_auc")
        cv_auc[name] = {"mean": float(s.mean()), "std": float(s.std()),
                        "min": float(s.min()), "max": float(s.max())}

    perm = permutation_test(X, y, types, n_perm=n_perm, seed=seed)
    uni = univariate_table(X, y, types)
    n_sig = sum(r["significant_after_correction"] for r in uni)

    report = {"rows": int(len(X)), "features": int(X.shape[1]), "prevalence": float(y.mean()),
              "cross_validated_auc_3x5": cv_auc, "permutation_test": perm,
              "univariate": uni, "features_significant_after_bonferroni": int(n_sig)}
    if holdout_proba is not None and holdout_y is not None:
        lo, hi = bootstrap_auc_ci(holdout_y, holdout_proba)
        report["holdout_auc"] = float(roc_auc_score(holdout_y, holdout_proba))
        report["holdout_auc_95ci"] = [lo, hi]

    best_cv = max(v["mean"] for v in cv_auc.values())
    has_signal = perm["p_value"] < 0.01 and best_cv >= 0.60
    if has_signal:
        verdict = "SIGNAL_PRESENT"
    elif perm["p_value"] >= 0.05 and n_sig == 0:
        verdict = "NO_DETECTABLE_SIGNAL"
    else:
        verdict = "WEAK_SIGNAL"
    report["verdict"] = verdict
    report["verdict_explained"] = {
        "SIGNAL_PRESENT": "Cross-validated AUC is clearly above what shuffled labels produce.",
        "WEAK_SIGNAL": "Some evidence of signal but too weak to support useful prediction (best CV AUC < 0.60 "
                       "or permutation p >= 0.01).",
        "NO_DETECTABLE_SIGNAL": "Cross-validated AUC is indistinguishable from shuffled labels and no feature "
                                "is significant after correction. The features do not predict the target in this "
                                "dataset. The shift monitor can still be evaluated as a data-compatibility mechanism, "
                                "but this evidence does not show that it protects a useful prediction model.",
    }[verdict]

    report = to_builtin(report)
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "validation_report.json").write_text(json.dumps(report, indent=2))
        (out_dir / "validation_report.md").write_text(render_markdown(report))
    return report


def render_markdown(r: dict) -> str:
    p = r["permutation_test"]
    lines = [f"# Dataset validation report", "",
             f"**Verdict: {r['verdict']}** — {r['verdict_explained']}", "",
             f"Rows: {r['rows']} · features: {r['features']} · prevalence: {r['prevalence']:.3f}", "",
             "## Cross-validated ROC-AUC (5-fold x 3 repeats)", "",
             "| Model | mean | std | min | max |", "|---|---|---|---|---|"]
    for k, v in r["cross_validated_auc_3x5"].items():
        lines.append(f"| {k} | {v['mean']:.3f} | {v['std']:.3f} | {v['min']:.3f} | {v['max']:.3f} |")
    lines += ["", "## Label-permutation test (logistic regression)", "",
              f"Observed CV AUC {p['observed_cv_auc']:.3f}; shuffled-label AUC averages {p['null_mean']:.3f} "
              f"(95th percentile {p['null_95th_percentile']:.3f}); p = {p['p_value']:.3f} "
              f"over {p['n_permutations']} permutations.", ""]
    if "holdout_auc" in r:
        lo, hi = r["holdout_auc_95ci"]
        lines += ["## Held-out test AUC", "", f"{r['holdout_auc']:.3f} (bootstrap 95% CI {lo:.3f}–{hi:.3f}). "
                  "An interval containing 0.5 means the model is not distinguishable from chance.", ""]
    lines += ["## Univariate tests (Mann-Whitney, Bonferroni-corrected)", "",
              f"{r['features_significant_after_bonferroni']} of {len(r['univariate'])} features significant "
              "after correction.", "", "| Feature | AUC | p | p (Bonferroni) |", "|---|---|---|---|"]
    for u in r["univariate"]:
        lines.append(f"| {u['feature']} | {u['auc']:.3f} | {u['p_value']:.3f} | {u['p_bonferroni']:.3f} |")
    return "\n".join(lines) + "\n"
