"""Distribution-shift monitoring: PSI, KS / chi-square tests and missingness.

Design notes
* Low-cardinality numeric features (<=10 distinct values, e.g. 0/1 flags) are monitored as
  discrete categories. Quantile-binned PSI collapses to a single bin on binary columns and
  would silently never fire.
* Statistical tests only flag when BOTH the Bonferroni-adjusted p-value is significant AND the
  effect size is non-trivial, because with thousands of reference rows tiny changes are
  "significant".
* Shift status is a statement about INPUTS. It never claims accuracy has dropped.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

EPS = 1e-4
DISCRETE_MAX_UNIQUE = 10
KS_SAMPLE = 2000


@dataclass(frozen=True)
class MonitorConfig:
    psi_moderate: float = 0.20
    psi_major: float = 0.50
    alpha: float = 0.05
    min_effect: float = 0.10
    missing_delta: float = 0.05
    min_batch: int = 300
    flagged_fraction_major: float = 0.30
    unseen_rate: float = 0.02


def _key(value) -> str:
    if isinstance(value, (bool, np.bool_)):
        return str(int(value))
    if isinstance(value, (int, float, np.integer, np.floating)):
        return format(float(value), "g")
    return str(value)


def _norm(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), EPS, None)
    return p / p.sum()


def psi_from_props(ref_props, cur_props) -> float:
    r, c = _norm(ref_props), _norm(cur_props)
    return float(np.sum((c - r) * np.log(c / r)))


def build_reference(X: pd.DataFrame, types: dict[str, str], seed: int = 42) -> dict:
    """Summarise the (coerced) training features into a compact monitoring reference."""
    rng = np.random.default_rng(seed)
    reference = {}
    for col in X.columns:
        s = X[col]
        non_null = s.dropna()
        if non_null.empty:
            raise ValueError(f"Feature '{col}' is entirely missing in the training data.")
        entry = {"missing_rate": float(s.isna().mean()), "n": int(len(s))}
        if types[col] == "numeric":
            vals = non_null.to_numpy(float)
            inner = np.unique(np.quantile(vals, np.linspace(0.1, 0.9, 9)))
            if len(np.unique(vals)) > DISCRETE_MAX_UNIQUE and len(inner) >= 2:
                idx = np.searchsorted(inner, vals, side="right")
                counts = np.bincount(idx, minlength=len(inner) + 1)
                size = min(len(vals), KS_SAMPLE)
                sample = np.sort(rng.choice(vals, size=size, replace=False))
                lo, hi = float(vals.min()), float(vals.max())
                pad = 0.1 * (hi - lo)
                entry.update(kind="continuous", inner_edges=inner.tolist(),
                             ref_props=(counts / counts.sum()).tolist(),
                             ks_sample=sample.tolist(), min=lo, max=hi,
                             range_low=lo - pad, range_high=hi + pad,
                             mean=float(vals.mean()), std=float(vals.std()))
            else:
                counts = pd.Series([_key(v) for v in vals]).value_counts()
                entry.update(kind="discrete", counts={k: int(v) for k, v in counts.items()},
                             min=float(vals.min()), max=float(vals.max()),
                             mean=float(vals.mean()), std=float(vals.std()))
        else:
            counts = non_null.astype(str).value_counts()
            entry.update(kind="categorical", counts={k: int(v) for k, v in counts.items()})
        reference[col] = entry
    return reference


class ShiftMonitor:
    def __init__(self, reference: dict, config: MonitorConfig | None = None):
        self.reference = reference
        self.config = config or MonitorConfig()

    # -- per feature ---------------------------------------------------------------
    def _feature(self, col: str, s: pd.Series, n_features: int) -> dict:
        cfg, ref = self.config, self.reference[col]
        non_null = s.dropna()
        cur_missing = float(s.isna().mean()) if len(s) else float("nan")
        res = {"feature": col, "kind": ref["kind"], "psi": None, "test": None,
               "statistic": None, "p_value": None, "effect_size": None, "unseen_rate": 0.0,
               "ref_missing_rate": ref["missing_rate"], "cur_missing_rate": cur_missing,
               "missing_delta": cur_missing - ref["missing_rate"]}

        if len(non_null) > 0:
            if ref["kind"] == "continuous":
                vals = non_null.to_numpy(float)
                inner = np.asarray(ref["inner_edges"])
                counts = np.bincount(np.searchsorted(inner, vals, side="right"),
                                     minlength=len(inner) + 1)
                res["psi"] = psi_from_props(ref["ref_props"], counts / counts.sum())
                if len(vals) >= 2:
                    ks = stats.ks_2samp(ref["ks_sample"], vals)
                    res.update(test="ks", statistic=float(ks.statistic),
                               p_value=float(ks.pvalue), effect_size=float(ks.statistic))
            else:
                if ref["kind"] == "discrete":
                    keys = [_key(v) for v in non_null.to_numpy(float)]
                else:
                    keys = non_null.astype(str).tolist()
                cur = pd.Series(keys).value_counts()
                cats = sorted(set(ref["counts"]) | set(cur.index))
                ref_c = np.array([ref["counts"].get(c, 0) for c in cats], float)
                cur_c = np.array([cur.get(c, 0) for c in cats], float)
                res["psi"] = psi_from_props(ref_c / ref_c.sum(), cur_c / cur_c.sum())
                unseen = [c for c in cats if c not in ref["counts"]]
                res["unseen_rate"] = float(sum(cur.get(c, 0) for c in unseen) / cur_c.sum())
                table = np.vstack([ref_c, cur_c])
                table = table[:, table.sum(axis=0) > 0]
                if table.shape[1] >= 2:
                    chi2, p, _, _ = stats.chi2_contingency(table)
                    res.update(test="chi2", statistic=float(chi2), p_value=float(p),
                               effect_size=float(math.sqrt(chi2 / table.sum())))

        psi = res["psi"]
        alpha_adj = cfg.alpha / max(1, n_features)
        res["psi_flag"] = psi is not None and psi >= cfg.psi_moderate
        res["stat_flag"] = (res["p_value"] is not None and res["p_value"] < alpha_adj
                            and res["effect_size"] >= cfg.min_effect)
        res["missing_flag"] = abs(res["missing_delta"]) >= cfg.missing_delta
        res["unseen_flag"] = res["unseen_rate"] >= cfg.unseen_rate
        major = (psi is not None and psi >= cfg.psi_major) or abs(res["missing_delta"]) >= 4 * cfg.missing_delta
        any_flag = res["psi_flag"] or res["stat_flag"] or res["missing_flag"] or res["unseen_flag"]
        res["severity"] = "major" if major else ("moderate" if any_flag else "none")
        res["shift_detected"] = res["severity"] != "none"
        return res

    # -- batch ---------------------------------------------------------------------
    def compare(self, X: pd.DataFrame) -> dict:
        cfg, n = self.config, len(X)
        if n < cfg.min_batch:
            return {"status": "INSUFFICIENT_DATA", "n_rows": n, "min_batch": cfg.min_batch,
                    "features_checked": 0, "flagged_features": [], "major_features": [],
                    "detectors": {}, "results": [],
                    "message": (f"Batch has {n} rows; at least {cfg.min_batch} are needed for "
                                "meaningful distribution monitoring.")}
        n_features = len(self.reference)
        results = [self._feature(col, X[col], n_features) for col in self.reference]
        flagged = [r["feature"] for r in results if r["shift_detected"]]
        major = [r["feature"] for r in results if r["severity"] == "major"]
        if major or len(flagged) / n_features >= cfg.flagged_fraction_major:
            status = "MAJOR_SHIFT"
        elif flagged:
            status = "MODERATE_SHIFT"
        else:
            status = "NO_SHIFT_DETECTED"
        detectors = {
            "psi_moderate": any(r["psi_flag"] for r in results),
            "psi_major": any(r["psi"] is not None and r["psi"] >= cfg.psi_major for r in results),
            "statistical": any(r["stat_flag"] for r in results),
            "missingness": any(r["missing_flag"] for r in results),
            "unseen_category": any(r["unseen_flag"] for r in results),
        }
        return {"status": status, "n_rows": n, "features_checked": n_features,
                "flagged_features": flagged, "major_features": major,
                "detectors": detectors, "results": results,
                "message": ("Input shift does not by itself prove reduced accuracy; confirm with "
                            "labelled outcomes when they become available.")}
