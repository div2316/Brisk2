"""Combine model quality, input-shift status, record-level flags and (optional) labelled
performance into one honest reliability statement."""
from __future__ import annotations

import math

DISCLAIMER = ("Research prototype. Not a medical device and not for clinical decisions. "
              "A shift warning concerns the inputs; it does not by itself show that accuracy has fallen.")


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def model_quality(test_metrics: dict) -> dict:
    auc = test_metrics.get("roc_auc")
    if not _ok(auc):
        return {"level": "UNKNOWN", "roc_auc": None}
    level = "WEAK" if auc < 0.60 else "MODERATE" if auc < 0.70 else "ADEQUATE"
    return {"level": level, "roc_auc": float(auc)}


def labelled_check(baseline: dict, observed: dict, auc_drop: float, brier_increase: float) -> dict:
    """Compare performance measured on labelled incoming data with held-out baseline."""
    findings, degraded = [], False
    if _ok(baseline.get("roc_auc")) and _ok(observed.get("roc_auc")):
        drop = baseline["roc_auc"] - observed["roc_auc"]
        if drop >= auc_drop:
            degraded = True
            findings.append(f"ROC-AUC fell by {drop:.3f}")
    if _ok(baseline.get("brier")) and _ok(observed.get("brier")):
        inc = observed["brier"] - baseline["brier"]
        if inc >= brier_increase:
            degraded = True
            findings.append(f"Brier score rose by {inc:.3f}")
    return {"performance_degraded": degraded, "findings": findings,
            "baseline": {k: baseline.get(k) for k in ("roc_auc", "pr_auc", "brier", "recall", "precision")},
            "observed": observed}


def combine(quality: dict, shift: dict, flagged_records: int, n_records: int,
            labelled: dict | None) -> dict:
    reasons: list[str] = []
    level = "HIGH"
    shift_status = shift["status"]

    if quality["level"] == "WEAK":
        level = "LOW"
        reasons.append("Baseline held-out ROC-AUC is below 0.60: the model is close to uninformative.")
    elif quality["level"] == "MODERATE":
        level = "CAUTION"
        reasons.append("Baseline held-out ROC-AUC is below 0.70: discrimination is only moderate.")
    elif quality["level"] == "UNKNOWN":
        level = "CAUTION"
        reasons.append("Baseline model quality could not be determined.")

    def raise_to(new: str):
        nonlocal level
        order = ["HIGH", "CAUTION", "LOW"]
        if order.index(new) > order.index(level):
            level = new

    if shift_status == "MAJOR_SHIFT":
        raise_to("LOW")
        reasons.append("Major input distribution shift vs training data in: "
                       + ", ".join(shift["flagged_features"]) + ".")
    elif shift_status == "MODERATE_SHIFT":
        raise_to("CAUTION")
        reasons.append("Moderate input shift detected in: " + ", ".join(shift["flagged_features"]) + ".")
    elif shift_status == "INSUFFICIENT_DATA":
        reasons.append(shift["message"])

    if n_records and flagged_records / n_records > 0.20:
        raise_to("CAUTION")
        reasons.append(f"{flagged_records} of {n_records} records contain unusual inputs and need review.")
    elif flagged_records:
        reasons.append(f"{flagged_records} record(s) contain unusual inputs and need review.")

    if labelled is not None:
        if labelled["performance_degraded"]:
            raise_to("LOW")
            reasons.append("Measured performance on labelled data is degraded: "
                           + "; ".join(labelled["findings"]) + ".")
        else:
            reasons.append("Measured performance on labelled data is within tolerance of the baseline.")

    if level == "HIGH" and shift_status == "INSUFFICIENT_DATA" and labelled is None:
        level = "UNDETERMINED"
    if level == "HIGH":
        reasons.append("No shift, unusual inputs or performance loss detected.")

    action = {"HIGH": "Predictions can be shown with the standard research-use disclaimer.",
              "UNDETERMINED": "Submit larger batches (or labelled data) to assess reliability.",
              "CAUTION": "Show predictions with a visible warning and review flagged records/features.",
              "LOW": "Do not rely on these predictions; investigate the data source and revalidate the model."}[level]
    return {"level": level, "reasons": reasons, "recommended_action": action,
            "model_quality": quality, "shift_status": shift_status,
            "labelled_check_performed": labelled is not None, "disclaimer": DISCLAIMER}
