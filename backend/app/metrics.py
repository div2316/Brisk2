from __future__ import annotations

import numpy as np
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score,
                             precision_score, recall_score, roc_auc_score)


def expected_calibration_error(y, p, bins: int = 10) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=False), 0, bins - 1)
    ece = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            ece += mask.mean() * abs(y[mask].mean() - p[mask].mean())
    return float(ece)


def compute_metrics(y, p, threshold: float) -> dict:
    y = np.asarray(y).astype(int)
    p = np.clip(np.asarray(p, float), 0.0, 1.0)
    pred = (p >= threshold).astype(int)
    two_classes = len(np.unique(y)) == 2
    return {
        "n": int(len(y)),
        "prevalence": float(y.mean()),
        "roc_auc": float(roc_auc_score(y, p)) if two_classes else float("nan"),
        "pr_auc": float(average_precision_score(y, p)) if two_classes else float("nan"),
        "brier": float(brier_score_loss(y, p)),
        "ece": expected_calibration_error(y, p),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "accuracy": float((pred == y).mean()),
    }
