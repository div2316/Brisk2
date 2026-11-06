"""Exploratory region-wise drift audit using held-out rows from the trained dataset.

This is a within-dataset stress test, not external regional validation. It compares each
region's held-out rows with the pooled training reference and reports results both including
the region identifier and excluding it from the clinical-feature comparison.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .monitoring import MonitorConfig, ShiftMonitor
from .utils import to_builtin


def run_regional_audit(artifact_dir, region_column: str = "State_Name",
                       min_region_rows: int = 30, config: MonitorConfig | None = None) -> dict:
    artifact_dir = Path(artifact_dir)
    artifact = joblib.load(artifact_dir / "cvd_model.joblib")
    holdout_path = artifact_dir / "holdout.csv"
    if not holdout_path.exists():
        raise FileNotFoundError(f"Holdout file not found: {holdout_path}")
    holdout = pd.read_csv(holdout_path)
    features = artifact["features"]
    if region_column not in features:
        raise ValueError(f"Region column {region_column!r} is not a model feature. Available: {features}")
    X = holdout[features].copy()
    operational_config = config or MonitorConfig()
    # Regional held-out groups are smaller than the production batch minimum. Use a lower
    # minimum only for descriptive subgroup analysis, and explicitly report that limitation.
    audit_config = MonitorConfig(
        psi_moderate=operational_config.psi_moderate,
        psi_major=operational_config.psi_major,
        alpha=operational_config.alpha,
        min_effect=operational_config.min_effect,
        missing_delta=operational_config.missing_delta,
        min_batch=min_region_rows,
        flagged_fraction_major=operational_config.flagged_fraction_major,
        unseen_rate=operational_config.unseen_rate,
    )
    monitor_all = ShiftMonitor(artifact["reference"], audit_config)
    clinical_reference = {k: v for k, v in artifact["reference"].items() if k != region_column}
    monitor_clinical = ShiftMonitor(clinical_reference, audit_config)

    rows = []
    for region, group in X.groupby(region_column, dropna=False, sort=True):
        group = group.reset_index(drop=True)
        if len(group) < min_region_rows:
            continue
        all_report = monitor_all.compare(group)
        clinical_group = group.drop(columns=[region_column])
        clinical_report = monitor_clinical.compare(clinical_group)
        clinical_results = clinical_report.get("results", [])
        rows.append({
            "region": str(region),
            "n_holdout_rows": int(len(group)),
            "all_feature_status": all_report.get("status"),
            "all_feature_flagged": ", ".join(all_report.get("flagged_features", [])),
            "clinical_feature_status": clinical_report.get("status"),
            "clinical_feature_flagged": ", ".join(clinical_report.get("flagged_features", [])),
            "clinical_feature_major": ", ".join(clinical_report.get("major_features", [])),
            "clinical_max_psi": max([float(r.get("psi") or 0) for r in clinical_results], default=0.0),
            "clinical_feature_count_flagged": len(clinical_report.get("flagged_features", [])),
            "interpretation": (
                "Region label included; expected to differ from pooled all-region reference."
                if all_report.get("status") in {"MODERATE_SHIFT", "MAJOR_SHIFT"}
                else "No shift detected by this monitor."
            ),
        })
    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        result_df.to_csv(artifact_dir / "regional_shift_audit.csv", index=False)
    counts = result_df["clinical_feature_status"].value_counts().to_dict() if not result_df.empty else {}
    report = {
        "region_column": region_column,
        "n_regions_evaluated": int(len(result_df)),
        "min_region_rows": int(min_region_rows),
        "operational_min_batch": int(operational_config.min_batch),
        "total_holdout_rows": int(len(holdout)),
        "regions_by_clinical_feature_status": {str(k): int(v) for k, v in counts.items()},
        "source": artifact.get("audit", {}).get("source_file"),
        "limitation": (
            "This audit partitions held-out rows from the same source dataset by region and compares each "
            "subgroup with a pooled training reference. The audit lowers the minimum batch size to "
            f"{min_region_rows} for descriptive subgroup analysis, but the production firewall requires "
            f"{operational_config.min_batch} rows; these per-state results are not operational predictions. "
            "It is not an independent external validation and does not prove a regional shift causes performance loss. "
            "The all-feature monitor includes the "
            "region label, which will naturally differ in a single-region batch; the clinical-only view "
            "excludes that identifier to show shifts in the remaining patient features."
        ),
    }
    (artifact_dir / "regional_shift_audit.json").write_text(json.dumps(to_builtin(report), indent=2))
    md = [
        "# CardioGuard regional shift audit",
        "",
        f"- Region column: `{region_column}`",
        f"- Regions evaluated: {len(result_df)}",
        f"- Held-out rows: {len(holdout)}",
        "",
        "## Results",
        "",
        "Each region's held-out rows are compared with the pooled training reference. The all-feature status includes the region label; the clinical-feature status excludes that label so the reader can see whether other inputs also differ. The audit uses a lower sample minimum for descriptive analysis than the production firewall, so these subgroup statuses do not override the production minimum-batch rule.",
        "",
    ]
    if not result_df.empty:
        cols = list(result_df.columns)
        md.append("| " + " | ".join(cols) + " |")
        md.append("| " + " | ".join(["---"] * len(cols)) + " |")
        for _, row in result_df.iterrows():
            values = [str(row[c]).replace("|", "\\\\|").replace("\\n", " ") for c in cols]
            md.append("| " + " | ".join(values) + " |")
    md += [
        "",
        "## Interpretation limits",
        "",
        report["limitation"],
        "",
        "A detected distribution difference is a compatibility warning, not proof that predictions are incorrect. Clinical performance degradation requires labelled outcomes for the relevant region and an explicit comparison against the reference performance.",
    ]
    (artifact_dir / "regional_shift_audit.md").write_text("\\n".join(md) + "\\n")
    return to_builtin({"summary": report, "rows": rows})
