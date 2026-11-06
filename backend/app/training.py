"""Dataset audit, model comparison, calibration, threshold selection and artifact export."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict, cross_validate, train_test_split
from sklearn.pipeline import Pipeline

from .metrics import compute_metrics
from .monitoring import build_reference
from .preprocessing import build_preprocessor, coerce_frame, infer_feature_types
from .utils import sha256_file, to_builtin

log = logging.getLogger(__name__)
STATUS = "RESEARCH_PROTOTYPE_NOT_FOR_CLINICAL_USE"
NA_TOKENS = ["?", "NA", "N/A", "na", "n/a", "null", "NULL", "None", ""]
TRUE_TOKENS = {"1", "1.0", "true", "True", "TRUE"}
FALSE_TOKENS = {"0", "0.0", "false", "False", "FALSE"}


def encode_target(y: pd.Series, positive_label=None) -> pd.Series:
    values = list(pd.unique(y.dropna()))
    if len(values) != 2:
        raise ValueError(f"Target must have exactly 2 classes, found {len(values)}: {values[:10]}. "
                         "Binarise it first (e.g. disease present vs absent).")
    strs = {str(v) for v in values}
    if positive_label is not None:
        if str(positive_label) not in strs:
            raise ValueError(f"positive_label {positive_label!r} not found in target values {sorted(strs)}")
        pos = str(positive_label)
    elif strs <= (TRUE_TOKENS | FALSE_TOKENS):
        pos = next(s for s in strs if s in TRUE_TOKENS)
    else:
        raise ValueError(f"Target values {sorted(strs)} are not 0/1; pass positive_label.")
    return y.map(lambda v: str(v) == pos).astype(int)


def _single_feature_scores(X: pd.DataFrame, y: pd.Series, types: dict) -> dict[str, float]:
    scores = {}
    for col in X.columns:
        s = X[col]
        if types[col] == "numeric":
            score = s.fillna(s.median())
        else:
            means = y.groupby(s.fillna("__MISSING__")).mean()
            score = s.fillna("__MISSING__").map(means)
        if score.nunique() < 2:
            continue
        auc = roc_auc_score(y, score)
        scores[col] = float(max(auc, 1 - auc))
    return scores


def _candidates(seed: int) -> dict:
    return {
        "logistic_regression": LogisticRegression(max_iter=3000, random_state=seed),
        "random_forest": RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                                random_state=seed, n_jobs=1),
        "hist_gradient_boosting": HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05,
                                                                 random_state=seed),
    }


def _pick_threshold(y, p, strategy: str) -> float:
    grid = np.linspace(0.05, 0.95, 91)
    y = np.asarray(y)
    best_t, best_score = 0.5, -1.0
    for t in grid:
        pred = p >= t
        tp = float(((pred == 1) & (y == 1)).sum())
        fp = float(((pred == 1) & (y == 0)).sum())
        fn = float(((pred == 0) & (y == 1)).sum())
        tn = float(((pred == 0) & (y == 0)).sum())
        recall = tp / max(tp + fn, 1)
        if strategy == "youden":
            score = recall + tn / max(tn + fp, 1) - 1
        elif strategy == "recall90":
            if recall < 0.90:
                continue
            score = t  # highest threshold that still keeps recall >= 0.90
        else:
            score = 2 * tp / max(2 * tp + fp + fn, 1)
        if score > best_score:
            best_t, best_score = float(t), score
    return best_t


def train(csv_path, target: str, id_columns=(), positive_label=None, out_dir=None, seed: int = 42,
          test_size: float = 0.2, threshold_strategy: str = "f1", allow_suspicious: bool = False,
          drop_columns=(), profile: str = "custom") -> dict:
    csv_path = Path(csv_path)
    out_dir = Path(out_dir or Path(__file__).resolve().parent.parent / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)

    data = pd.read_csv(csv_path, na_values=NA_TOKENS, skipinitialspace=True)
    data.columns = data.columns.astype(str).str.strip()
    if target not in data.columns:
        raise ValueError(f"Target '{target}' not found. Columns: {data.columns.tolist()}")
    audit = {"source_file": csv_path.name, "rows_raw": int(len(data)), "warnings": []}
    # Dataset-specific quality/provenance notes for the supplied India risk-label file.
    if target == "Heart_Attack_Risk":
        audit["warnings"].append(
            "Target provenance is not verified by the CSV: treat Heart_Attack_Risk as the dataset-provided "
            "risk label, not a documented future heart-attack event with a defined follow-up horizon."
        )
    if {"Systolic_BP", "Diastolic_BP"}.issubset(data.columns):
        bp_bad = int((pd.to_numeric(data["Systolic_BP"], errors="coerce") <=
                      pd.to_numeric(data["Diastolic_BP"], errors="coerce")).fillna(False).sum())
        if bp_bad:
            audit["warnings"].append(
                f"{bp_bad} rows have Systolic_BP <= Diastolic_BP; verify these against the source data dictionary "
                "before clinical interpretation. Values were not automatically changed."
            )

    data = data.dropna(subset=[target])
    audit["rows_after_dropping_missing_target"] = int(len(data))
    before = len(data)
    data = data.drop_duplicates().reset_index(drop=True)
    audit["duplicate_rows_removed"] = int(before - len(data))

    y = encode_target(data[target], positive_label)
    drop = [target, *[c for c in id_columns if c in data.columns], *[c for c in drop_columns if c in data.columns]]
    X = data.drop(columns=drop)
    for col in list(X.columns):
        if X[col].nunique(dropna=True) <= 1:
            audit["warnings"].append(f"Dropped constant column '{col}'.")
            X = X.drop(columns=col)
        elif (not pd.api.types.is_numeric_dtype(X[col])) and X[col].nunique() / len(X) > 0.95:
            audit["warnings"].append(f"Dropped ID-like column '{col}'.")
            X = X.drop(columns=col)
    if X.empty:
        raise ValueError("No input features remain after cleaning.")

    types = infer_feature_types(X)
    X, _ = coerce_frame(X, types)
    counts = y.value_counts()
    audit["class_counts"] = {str(k): int(v) for k, v in counts.items()}
    if counts.min() < 25:
        raise ValueError(f"Minority class has only {counts.min()} rows; need at least 25.")

    suspects = {k: v for k, v in _single_feature_scores(X, y, types).items() if v >= 0.98}
    audit["leakage_suspects"] = suspects
    if suspects and not allow_suspicious:
        raise ValueError(f"Possible target leakage (single-feature AUC >= 0.98): {suspects}. "
                         "Remove these columns or pass allow_suspicious=True.")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, stratify=y, random_state=seed)
    skf = StratifiedKFold(5, shuffle=True, random_state=seed)
    preprocessor = build_preprocessor(types)

    # -- compare candidates by cross-validation on the training split only ----------
    cv_results = {}
    pool = _candidates(seed)
    if len(X_train) > 20000:  # keep training time reasonable on large files
        pool.pop("random_forest", None)
    for name, estimator in pool.items():
        pipe = Pipeline([("pre", clone(preprocessor)), ("clf", estimator)])
        scores = cross_validate(pipe, X_train, y_train, cv=skf, error_score="raise",
                                scoring={"roc_auc": "roc_auc", "pr_auc": "average_precision",
                                         "brier": "neg_brier_score"})
        cv_results[name] = {"roc_auc_mean": float(scores["test_roc_auc"].mean()),
                            "roc_auc_std": float(scores["test_roc_auc"].std()),
                            "pr_auc_mean": float(scores["test_pr_auc"].mean()),
                            "brier_mean": float(-scores["test_brier"].mean())}
        log.info("CV %s: %s", name, cv_results[name])
    best = max(cv_results, key=lambda k: (round(cv_results[k]["roc_auc_mean"], 4), -cv_results[k]["brier_mean"]))

    pipe = Pipeline([("pre", clone(preprocessor)), ("clf", _candidates(seed)[best])])
    calibrated = CalibratedClassifierCV(estimator=pipe, method="sigmoid", cv=skf)
    calibrated.fit(X_train, y_train)

    oof = cross_val_predict(CalibratedClassifierCV(estimator=clone(pipe), method="sigmoid", cv=skf),
                            X_train, y_train, cv=StratifiedKFold(5, shuffle=True, random_state=seed + 1),
                            method="predict_proba")[:, 1]
    threshold = _pick_threshold(y_train.to_numpy(), oof, threshold_strategy)

    test_metrics = compute_metrics(y_test, calibrated.predict_proba(X_test)[:, 1], threshold)
    uncal = clone(pipe).fit(X_train, y_train)
    uncal_metrics = compute_metrics(y_test, uncal.predict_proba(X_test)[:, 1], 0.5)
    if test_metrics["roc_auc"] < 0.60:
        audit["warnings"].append("Held-out ROC-AUC < 0.60: model is near-random. Investigate the data "
                                 "before interpreting any shift experiment.")

    test_proba = calibrated.predict_proba(X_test)[:, 1]
    flagged_rate = float((test_proba >= threshold).mean())
    test_metrics["flagged_rate"] = flagged_rate
    if flagged_rate >= 0.95 or flagged_rate <= 0.05:
        audit["warnings"].append(
            f"Chosen threshold {threshold:.2f} classifies {flagged_rate:.0%} of held-out patients as one class: "
            "the classifier is degenerate (typical when the model has no real signal). "
            "Use probabilities, not the class label, and do not report accuracy/recall from this threshold.")

    imp = permutation_importance(calibrated, X_test, y_test, scoring="roc_auc",
                                 n_repeats=5, random_state=seed, n_jobs=1)
    importance = dict(sorted(zip(X.columns, map(float, imp.importances_mean)), key=lambda kv: -kv[1]))

    reference = build_reference(X_train, types, seed)
    # Typical value of every input (median / most frequent); used to explain individual predictions.
    baseline = {}
    for col in X.columns:
        if types[col] == "numeric":
            baseline[col] = float(X_train[col].median())
        else:
            baseline[col] = str(X_train[col].mode(dropna=True).iloc[0])
    evaluation = {"test": test_metrics, "test_uncalibrated_at_0.5": uncal_metrics,
                  "cross_validation": cv_results, "n_train": int(len(X_train)),
                  "n_test": int(len(X_test)), "threshold_strategy": threshold_strategy}
    artifact = {
        "model": calibrated, "features": list(X.columns), "feature_types": types,
        "target": target, "positive_label": None if positive_label is None else str(positive_label),
        "selected_model": best, "threshold": threshold, "reference": reference, "baseline": baseline,
        "background": X_train.sample(n=min(60, len(X_train)), random_state=seed).reset_index(drop=True),
        "evaluation": evaluation, "feature_importance": importance, "audit": audit,
        "status": STATUS, "sklearn_version": sklearn.__version__, "profile": profile,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_sha256": sha256_file(csv_path),
    }

    path = out_dir / "cvd_model.joblib"
    tmp = path.with_suffix(".tmp")
    joblib.dump(artifact, tmp)
    os.replace(tmp, path)
    (out_dir / "cvd_model.joblib.sha256").write_text(sha256_file(path))

    holdout = X_test.copy()
    holdout[target] = y_test.to_numpy()
    holdout.to_csv(out_dir / "holdout.csv", index=False)
    meta = {k: v for k, v in artifact.items() if k not in ("model", "reference")}
    (out_dir / "metadata.json").write_text(json.dumps(to_builtin(meta), indent=2))
    return to_builtin(meta)
