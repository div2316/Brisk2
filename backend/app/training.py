
"""Dataset audit, model comparison, calibration, threshold selection and artifact export."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

# Limit CPU usage in restricted cloud containers such as Render.
# Set these before importing NumPy, sklearn, or joblib.
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import joblib
import numpy as np
import pandas as pd
import sklearn

from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_predict,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline

from .metrics import compute_metrics
from .monitoring import build_reference
from .preprocessing import (
    build_preprocessor,
    coerce_frame,
    infer_feature_types,
)
from .utils import sha256_file, to_builtin


log = logging.getLogger(__name__)

STATUS = "RESEARCH_PROTOTYPE_NOT_FOR_CLINICAL_USE"

NA_TOKENS = [
    "?", "NA", "N/A", "na", "n/a",
    "null", "NULL", "None", ""
]

TRUE_TOKENS = {"1", "1.0", "true", "True", "TRUE"}
FALSE_TOKENS = {"0", "0.0", "false", "False", "FALSE"}


def encode_target(y: pd.Series, positive_label=None) -> pd.Series:
    """Convert a binary target into 0 and 1."""

    values = list(pd.unique(y.dropna()))

    if len(values) != 2:
        raise ValueError(
            f"Target must have exactly 2 classes, found {len(values)}: "
            f"{values[:10]}. Binarise it first."
        )

    strs = {str(v) for v in values}

    if positive_label is not None:
        if str(positive_label) not in strs:
            raise ValueError(
                f"positive_label {positive_label!r} not found "
                f"in target values {sorted(strs)}"
            )

        pos = str(positive_label)

    elif strs <= (TRUE_TOKENS | FALSE_TOKENS):
        pos = next(s for s in strs if s in TRUE_TOKENS)

    else:
        raise ValueError(
            f"Target values {sorted(strs)} are not 0/1; "
            "pass positive_label."
        )

    return y.map(lambda v: str(v) == pos).astype(int)


def _single_feature_scores(
    X: pd.DataFrame,
    y: pd.Series,
    types: dict
) -> dict[str, float]:
    """Check whether an individual feature strongly predicts the target."""

    scores = {}

    for col in X.columns:
        s = X[col]

        if types[col] == "numeric":
            score = s.fillna(s.median())

        else:
            means = y.groupby(
                s.fillna("__MISSING__")
            ).mean()

            score = s.fillna("__MISSING__").map(means)

        if score.nunique() < 2:
            continue

        auc = roc_auc_score(y, score)

        scores[col] = float(max(auc, 1 - auc))

    return scores


def _candidates(seed: int) -> dict:
    """Return the candidate machine-learning models."""

    return {
        "logistic_regression": LogisticRegression(
            max_iter=3000,
            random_state=seed
        ),

        "random_forest": RandomForestClassifier(
            n_estimators=300,
            min_samples_leaf=3,
            random_state=seed,
            n_jobs=1
        ),

        "hist_gradient_boosting": HistGradientBoostingClassifier(
            max_iter=200,
            learning_rate=0.05,
            random_state=seed
        ),
    }


def _pick_threshold(y, p, strategy: str) -> float:
    """Select a classification threshold using training predictions."""

    grid = np.linspace(0.05, 0.95, 91)

    y = np.asarray(y)

    best_t = 0.5
    best_score = -1.0

    for t in grid:

        pred = p >= t

        tp = float(((pred == 1) & (y == 1)).sum())
        fp = float(((pred == 1) & (y == 0)).sum())
        fn = float(((pred == 0) & (y == 1)).sum())
        tn = float(((pred == 0) & (y == 0)).sum())

        recall = tp / max(tp + fn, 1)

        if strategy == "youden":

            specificity = tn / max(tn + fp, 1)
            score = recall + specificity - 1

        elif strategy == "recall90":

            if recall < 0.90:
                continue

            score = t

        else:

            score = (
                2 * tp /
                max(2 * tp + fp + fn, 1)
            )

        if score > best_score:
            best_t = float(t)
            best_score = score

    return best_t


def train(
    csv_path,
    target: str,
    id_columns=(),
    positive_label=None,
    out_dir=None,
    seed: int = 42,
    test_size: float = 0.2,
    threshold_strategy: str = "f1",
    allow_suspicious: bool = False,
    drop_columns=(),
    profile: str = "custom"
) -> dict:

    """Train, evaluate, calibrate and export the selected CVD model."""

    csv_path = Path(csv_path)

    out_dir = Path(
        out_dir or
        Path(__file__).resolve().parent.parent / "artifacts"
    )

    out_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------
    # 1. LOAD DATASET
    # ---------------------------------------------------------

    log.info("Loading dataset: %s", csv_path)

    data = pd.read_csv(
        csv_path,
        na_values=NA_TOKENS,
        skipinitialspace=True
    )

    data.columns = data.columns.astype(str).str.strip()

    if target not in data.columns:
        raise ValueError(
            f"Target '{target}' not found. "
            f"Columns: {data.columns.tolist()}"
        )

    audit = {
        "source_file": csv_path.name,
        "rows_raw": int(len(data)),
        "warnings": []
    }

    # Dataset-specific target provenance warning.
    if target == "Heart_Attack_Risk":

        audit["warnings"].append(
            "Target provenance is not verified by the CSV: "
            "treat Heart_Attack_Risk as the dataset-provided "
            "risk label, not a documented future heart-attack "
            "event with a defined follow-up horizon."
        )

    # ---------------------------------------------------------
    # 2. BASIC DATA QUALITY CHECKS
    # ---------------------------------------------------------

    if {
        "Systolic_BP",
        "Diastolic_BP"
    }.issubset(data.columns):

        systolic = pd.to_numeric(
            data["Systolic_BP"],
            errors="coerce"
        )

        diastolic = pd.to_numeric(
            data["Diastolic_BP"],
            errors="coerce"
        )

        bp_bad = int(
            (systolic <= diastolic).fillna(False).sum()
        )

        if bp_bad:

            audit["warnings"].append(
                f"{bp_bad} rows have Systolic_BP <= "
                "Diastolic_BP; verify these against the "
                "source data dictionary before clinical "
                "interpretation. Values were not automatically changed."
            )

    # Remove rows with missing target.
    data = data.dropna(subset=[target])

    audit["rows_after_dropping_missing_target"] = int(
        len(data)
    )

    # Remove duplicate rows.
    before = len(data)

    data = data.drop_duplicates().reset_index(drop=True)

    audit["duplicate_rows_removed"] = int(
        before - len(data)
    )

    # ---------------------------------------------------------
    # 3. TARGET ENCODING
    # ---------------------------------------------------------

    y = encode_target(
        data[target],
        positive_label
    )

    drop = [
        target,
        *[
            c for c in id_columns
            if c in data.columns
        ],
        *[
            c for c in drop_columns
            if c in data.columns
        ]
    ]

    X = data.drop(columns=drop)

    # ---------------------------------------------------------
    # 4. FEATURE CLEANING
    # ---------------------------------------------------------

    for col in list(X.columns):

        if X[col].nunique(dropna=True) <= 1:

            audit["warnings"].append(
                f"Dropped constant column '{col}'."
            )

            X = X.drop(columns=col)

        elif (
            not pd.api.types.is_numeric_dtype(X[col])
            and X[col].nunique() / len(X) > 0.95
        ):

            audit["warnings"].append(
                f"Dropped ID-like column '{col}'."
            )

            X = X.drop(columns=col)

    if X.empty:
        raise ValueError(
            "No input features remain after cleaning."
        )

    # Infer feature types and coerce values.
    types = infer_feature_types(X)

    X, _ = coerce_frame(X, types)

    # ---------------------------------------------------------
    # 5. CLASS DISTRIBUTION
    # ---------------------------------------------------------

    counts = y.value_counts()

    audit["class_counts"] = {
        str(k): int(v)
        for k, v in counts.items()
    }

    if counts.min() < 25:
        raise ValueError(
            f"Minority class has only {counts.min()} rows; "
            "need at least 25."
        )

    # ---------------------------------------------------------
    # 6. TARGET LEAKAGE CHECK
    # ---------------------------------------------------------

    suspects = {
        k: v
        for k, v in _single_feature_scores(
            X, y, types
        ).items()
        if v >= 0.98
    }

    audit["leakage_suspects"] = suspects

    if suspects and not allow_suspicious:

        raise ValueError(
            "Possible target leakage "
            f"(single-feature AUC >= 0.98): {suspects}. "
            "Remove these columns or pass allow_suspicious=True."
        )

    # ---------------------------------------------------------
    # 7. TRAIN-TEST SPLIT
    # ---------------------------------------------------------

    log.info("Splitting dataset into training and test sets.")

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=test_size,
        stratify=y,
        random_state=seed
    )

    skf = StratifiedKFold(
        n_splits=5,
        shuffle=True,
        random_state=seed
    )

    preprocessor = build_preprocessor(types)

    # ---------------------------------------------------------
    # 8. MODEL COMPARISON USING CROSS-VALIDATION
    # ---------------------------------------------------------

    log.info("Starting candidate model comparison.")

    cv_results = {}

    pool = _candidates(seed)

    if len(X_train) > 20000:
        pool.pop("random_forest", None)

    for name, estimator in pool.items():

        log.info("Training candidate: %s", name)

        pipe = Pipeline([
            ("pre", clone(preprocessor)),
            ("clf", estimator)
        ])

        scores = cross_validate(
            pipe,
            X_train,
            y_train,
            cv=skf,
            error_score="raise",
            n_jobs=1,
            scoring={
                "roc_auc": "roc_auc",
                "pr_auc": "average_precision",
                "brier": "neg_brier_score"
            }
        )

        cv_results[name] = {
            "roc_auc_mean": float(
                scores["test_roc_auc"].mean()
            ),
            "roc_auc_std": float(
                scores["test_roc_auc"].std()
            ),
            "pr_auc_mean": float(
                scores["test_pr_auc"].mean()
            ),
            "brier_mean": float(
                -scores["test_brier"].mean()
            )
        }

        log.info(
            "CV %s: %s",
            name,
            cv_results[name]
        )

    if not cv_results:
        raise RuntimeError(
            "No candidate models were successfully evaluated."
        )

    # Select the best candidate using CV ROC-AUC and Brier score.
    best = max(
        cv_results,
        key=lambda k: (
            round(cv_results[k]["roc_auc_mean"], 4),
            -cv_results[k]["brier_mean"]
        )
    )

    log.info("Selected model: %s", best)

    # ---------------------------------------------------------
    # 9. FINAL PIPELINE
    # ---------------------------------------------------------

    pipe = Pipeline([
        ("pre", clone(preprocessor)),
        ("clf", _candidates(seed)[best])
    ])

    # ---------------------------------------------------------
    # 10. PROBABILITY CALIBRATION
    # ---------------------------------------------------------

    log.info("Starting probability calibration.")

    calibrated = CalibratedClassifierCV(
        estimator=pipe,
        method="sigmoid",
        cv=skf,
        n_jobs=1
    )

    calibrated.fit(
        X_train,
        y_train
    )

    log.info("Probability calibration completed.")

    # ---------------------------------------------------------
    # 11. OUT-OF-FOLD PREDICTIONS
    # ---------------------------------------------------------

    log.info("Generating out-of-fold predictions.")

    oof_calibrator = CalibratedClassifierCV(
        estimator=clone(pipe),
        method="sigmoid",
        cv=skf,
        n_jobs=1
    )

    oof = cross_val_predict(
        oof_calibrator,
        X_train,
        y_train,
        cv=StratifiedKFold(
            n_splits=5,
            shuffle=True,
            random_state=seed + 1
        ),
        method="predict_proba",
        n_jobs=1
    )[:, 1]

    log.info("Out-of-fold predictions completed.")

    # ---------------------------------------------------------
    # 12. THRESHOLD SELECTION
    # ---------------------------------------------------------

    threshold = _pick_threshold(
        y_train.to_numpy(),
        oof,
        threshold_strategy
    )

    log.info(
        "Selected classification threshold: %.4f",
        threshold
    )

    # ---------------------------------------------------------
    # 13. HELD-OUT TEST EVALUATION
    # ---------------------------------------------------------

    log.info("Evaluating calibrated model on held-out test data.")

    test_proba = calibrated.predict_proba(
        X_test
    )[:, 1]

    test_metrics = compute_metrics(
        y_test,
        test_proba,
        threshold
    )

    # Uncalibrated comparison model.
    log.info("Evaluating uncalibrated model.")

    uncal = clone(pipe).fit(
        X_train,
        y_train
    )

    uncal_metrics = compute_metrics(
        y_test,
        uncal.predict_proba(X_test)[:, 1],
        0.5
    )

    if test_metrics["roc_auc"] < 0.60:

        audit["warnings"].append(
            "Held-out ROC-AUC < 0.60: model is near-random. "
            "Investigate the data before interpreting any "
            "shift experiment."
        )

    # Check the percentage of patients flagged positive.
    flagged_rate = float(
        (test_proba >= threshold).mean()
    )

    test_metrics["flagged_rate"] = flagged_rate

    if flagged_rate >= 0.95 or flagged_rate <= 0.05:

        audit["warnings"].append(
            f"Chosen threshold {threshold:.2f} classifies "
            f"{flagged_rate:.0%} of held-out patients as one class: "
            "the classifier is degenerate. Use probabilities, "
            "not the class label, and do not report accuracy/recall "
            "from this threshold."
        )

    log.info("Held-out evaluation completed.")

    # ---------------------------------------------------------
    # 14. FEATURE IMPORTANCE
    # ---------------------------------------------------------

    log.info("Calculating permutation feature importance.")

    imp = permutation_importance(
        calibrated,
        X_test,
        y_test,
        scoring="roc_auc",
        n_repeats=5,
        random_state=seed,
        n_jobs=1
    )

    importance = dict(
        sorted(
            zip(
                X.columns,
                map(float, imp.importances_mean)
            ),
            key=lambda kv: -kv[1]
        )
    )

    # ---------------------------------------------------------
    # 15. REFERENCE DATA FOR MONITORING
    # ---------------------------------------------------------

    reference = build_reference(
        X_train,
        types,
        seed
    )

    # ---------------------------------------------------------
    # 16. BASELINE FEATURE VALUES
    # ---------------------------------------------------------

    baseline = {}

    for col in X.columns:

        if types[col] == "numeric":

            baseline[col] = float(
                X_train[col].median()
            )

        else:

            baseline[col] = str(
                X_train[col].mode(
                    dropna=True
                ).iloc[0]
            )

    # ---------------------------------------------------------
    # 17. EVALUATION METADATA
    # ---------------------------------------------------------

    evaluation = {
        "test": test_metrics,
        "test_uncalibrated_at_0.5": uncal_metrics,
        "cross_validation": cv_results,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "threshold_strategy": threshold_strategy
    }

    # ---------------------------------------------------------
    # 18. MODEL ARTIFACT
    # ---------------------------------------------------------

    artifact = {
        "model": calibrated,
        "features": list(X.columns),
        "feature_types": types,
        "target": target,
        "positive_label": (
            None
            if positive_label is None
            else str(positive_label)
        ),
        "selected_model": best,
        "threshold": threshold,
        "reference": reference,
        "baseline": baseline,
        "background": X_train.sample(
            n=min(60, len(X_train)),
            random_state=seed
        ).reset_index(drop=True),
        "evaluation": evaluation,
        "feature_importance": importance,
        "audit": audit,
        "status": STATUS,
        "sklearn_version": sklearn.__version__,
        "profile": profile,
        "trained_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "data_sha256": sha256_file(csv_path)
    }

    # ---------------------------------------------------------
    # 19. EXPORT MODEL
    # ---------------------------------------------------------

    log.info("Exporting trained model artifact.")

    path = out_dir / "cvd_model.joblib"

    tmp = path.with_suffix(".tmp")

    joblib.dump(
        artifact,
        tmp
    )

    os.replace(
        tmp,
        path
    )

    # Save checksum.
    checksum = sha256_file(path)

    (out_dir / "cvd_model.joblib.sha256").write_text(
        checksum
    )

    # ---------------------------------------------------------
    # 20. EXPORT HOLDOUT DATA
    # ---------------------------------------------------------

    holdout = X_test.copy()

    holdout[target] = y_test.to_numpy()

    holdout.to_csv(
        out_dir / "holdout.csv",
        index=False
    )

    # ---------------------------------------------------------
    # 21. EXPORT METADATA
    # ---------------------------------------------------------

    meta = {
        k: v
        for k, v in artifact.items()
        if k not in ("model", "reference")
    }

    (out_dir / "metadata.json").write_text(
        json.dumps(
            to_builtin(meta),
            indent=2
        )
    )

    log.info("Model training and artifact export completed.")
    log.info("Selected model: %s", best)
    log.info("Threshold: %.4f", threshold)
    log.info("Model artifact: %s", path)

    return to_builtin(meta)
