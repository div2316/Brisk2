"""Model service: load a verified artifact once, then predict / monitor / assess."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .config import Settings, get_settings
from .metrics import compute_metrics
from .monitoring import ShiftMonitor
from .preprocessing import coerce_frame
from .reliability import DISCLAIMER, combine, labelled_check, model_quality
from .utils import sha256_file, to_builtin

log = logging.getLogger(__name__)


class ArtifactError(RuntimeError):
    pass


class CVDModelService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        path = self.settings.artifact_path
        if not path.exists():
            raise ArtifactError(f"Model artifact not found at {path}. Run `python -m app.cli train` first.")
        self._verify(path)
        self.artifact = joblib.load(path)
        self.model = self.artifact["model"]
        self.features: list[str] = self.artifact["features"]
        self.types: dict = self.artifact["feature_types"]
        self.threshold: float = float(self.artifact["threshold"])
        self.reference: dict = self.artifact["reference"]
        self.monitor = ShiftMonitor(self.reference, self.settings.monitor)
        self.baseline = self.artifact["evaluation"]["test"]
        self.quality = model_quality(self.baseline)

    def _verify(self, path: Path):
        sidecar = path.with_name(path.name + ".sha256")
        if sidecar.exists():
            if sidecar.read_text().strip() != sha256_file(path):
                raise ArtifactError("Model artifact checksum mismatch; refusing to load.")
        elif not self.settings.allow_unverified_artifact:
            raise ArtifactError("Checksum file missing; set ALLOW_UNVERIFIED_ARTIFACT=1 to override.")

    # -- input handling ------------------------------------------------------------
    def _prepare(self, records):
        if isinstance(records, dict):
            records = [records]
        frame = records if isinstance(records, pd.DataFrame) else pd.DataFrame(list(records))
        if frame.empty:
            raise ValueError("No records supplied.")
        if len(frame) > self.settings.max_records:
            raise ValueError(f"Too many records ({len(frame)}); maximum is {self.settings.max_records}.")
        if not frame.columns.is_unique:
            raise ValueError("Input contains duplicate column names.")
        frame.columns = frame.columns.astype(str).str.strip()
        missing = [c for c in self.features if c not in frame.columns]
        if missing:
            raise ValueError(f"Missing required features: {missing}. Use null for unknown values.")
        ignored = [c for c in frame.columns if c not in self.features]
        X, bad = coerce_frame(frame[self.features].reset_index(drop=True), self.types)
        return X, ignored, bad.reset_index(drop=True)

    def _record_flags(self, X: pd.DataFrame, bad: pd.DataFrame) -> list[dict]:
        reasons: list[list[str]] = [[] for _ in range(len(X))]
        for col in self.features:
            ref = self.reference[col]
            s = X[col]
            for i in np.flatnonzero(bad[col].to_numpy()):
                reasons[i].append(f"{col}: value could not be interpreted")
            if ref["kind"] == "continuous":
                mask = ((s < ref["range_low"]) | (s > ref["range_high"])).to_numpy()
                for i in np.flatnonzero(mask):
                    reasons[i].append(f"{col}: outside training range")
            elif ref["kind"] == "discrete":
                known = set(ref["counts"])
                for i, v in enumerate(s.to_numpy()):
                    if not np.isnan(v) and format(float(v), "g") not in known:
                        reasons[i].append(f"{col}: value never seen in training")
            else:
                known = set(ref["counts"])
                for i, v in enumerate(s.to_numpy()):
                    if isinstance(v, str) and v not in known:
                        reasons[i].append(f"{col}: category never seen in training")
        miss_frac = X.isna().mean(axis=1).to_numpy()
        for i in np.flatnonzero(miss_frac > 0.30):
            reasons[i].append(f"{miss_frac[i]:.0%} of features missing")
        return [{"index": i, "needs_review": bool(r), "reasons": r} for i, r in enumerate(reasons)]

    # -- public API ----------------------------------------------------------------
    def _predict_frame(self, X: pd.DataFrame, ignored, flags) -> list[dict]:
        proba = self.model.predict_proba(X)[:, 1]
        return [{"index": i, "estimated_probability": float(p),
                 "estimated_percentage": round(float(p) * 100, 2),
                 "predicted_class": int(p >= self.threshold),
                 "needs_review": flags[i]["needs_review"], "review_reasons": flags[i]["reasons"]}
                for i, p in enumerate(proba)]

    def predict(self, records) -> dict:
        X, ignored, bad = self._prepare(records)
        flags = self._record_flags(X, bad)
        return to_builtin({"predictions": self._predict_frame(X, ignored, flags),
                           "threshold": self.threshold, "ignored_columns": ignored,
                           "model_status": self.artifact["status"], "disclaimer": DISCLAIMER})

    def monitor_batch(self, records) -> dict:
        X, ignored, _ = self._prepare(records)
        return to_builtin({**self.monitor.compare(X), "ignored_columns": ignored})

    def assess(self, records, labels=None) -> dict:
        X, ignored, bad = self._prepare(records)
        flags = self._record_flags(X, bad)
        predictions = self._predict_frame(X, ignored, flags)
        shift = self.monitor.compare(X)
        flagged = sum(f["needs_review"] for f in flags)

        labelled = None
        if labels is not None:
            y = np.asarray(labels)
            if len(y) != len(X):
                raise ValueError("labels must have the same length as records.")
            if not set(np.unique(y)).issubset({0, 1}):
                raise ValueError("labels must contain only 0 and 1.")
            if len(X) >= self.monitor.config.min_batch and len(np.unique(y)) == 2:
                proba = np.array([p["estimated_probability"] for p in predictions])
                observed = compute_metrics(y, proba, self.threshold)
                labelled = labelled_check(self.baseline, observed, self.settings.auc_drop_threshold,
                                          self.settings.brier_increase_threshold)
        reliability = combine(self.quality, shift, flagged, len(X), labelled)
        result = {"predictions": predictions, "threshold": self.threshold,
                  "shift_report": shift, "labelled_performance": labelled,
                  "reliability": reliability, "ignored_columns": ignored,
                  "model_status": self.artifact["status"]}
        self._audit(len(X), shift["status"], reliability["level"])
        return to_builtin(result)

    def _audit(self, n: int, shift_status: str, level: str):
        """Append a PHI-free summary line (counts and statuses only)."""
        log.info("assess n=%d shift=%s reliability=%s", n, shift_status, level)
        path = self.settings.audit_log
        if path:
            try:
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(), "n": n,
                                         "shift": shift_status, "reliability": level}) + "\n")
            except OSError:
                log.warning("Could not write audit log", exc_info=True)

    def schema(self) -> dict:
        out = {}
        for col in self.features:
            ref = self.reference[col]
            item = {"type": self.types[col], "monitoring_kind": ref["kind"],
                    "training_missing_rate": ref["missing_rate"]}
            if ref["kind"] == "categorical":
                item["known_values"] = sorted(ref["counts"])
            elif ref["kind"] == "discrete":
                item["known_values"] = sorted(ref["counts"], key=float)
            else:
                item.update(training_min=ref["min"], training_max=ref["max"], training_mean=ref["mean"])
            out[col] = item
        return to_builtin(out)

    def metadata(self) -> dict:
        a = self.artifact
        return to_builtin({"target": a["target"], "selected_model": a["selected_model"],
                           "features": self.features, "threshold": self.threshold,
                           "evaluation": a["evaluation"], "model_quality": self.quality,
                           "feature_importance": a["feature_importance"], "audit": a["audit"],
                           "trained_at": a["trained_at"], "status": a["status"],
                           "monitoring_thresholds": asdict(self.monitor.config)})

    # -- single-patient prediction with explanation -------------------------------------
    BANDS = ((20.0, "Low"), (50.0, "Moderate"), (101.0, "High"))

    @classmethod
    def band(cls, risk_pct: float) -> str:
        for upper, name in cls.BANDS:
            if risk_pct < upper:
                return name
        return "High"

    def baseline_value(self, col: str):
        base = self.artifact.get("baseline") or {}
        if col in base:
            return base[col]
        ref = self.reference[col]
        if ref["kind"] == "categorical":
            return max(ref["counts"], key=ref["counts"].get)
        return ref["mean"]

    def explain_one(self, X: pd.DataFrame) -> list[dict]:
        """Shapley-style explanation (permutation sampling against a background sample of training rows).
        Each value is the average change in the estimated probability, in percentage points, when that input is
        added to a random mix of the other inputs. Contributions add up to (estimate - average background estimate)."""
        row = X.iloc[[0]]
        bg = self.artifact.get("background")
        if bg is None or len(bg) == 0:  # older artifacts: fall back to median/mode replacement
            return self._explain_occlusion(row)
        bg = bg[self.features].reset_index(drop=True)
        rng = np.random.default_rng(7)
        n_perm, n_bg, F = 24, min(12, len(bg)), len(self.features)
        contrib = np.zeros(F)
        frames, plan = [], []
        for _ in range(n_perm):
            order = rng.permutation(F)
            b = bg.iloc[rng.choice(len(bg), n_bg, replace=False)].reset_index(drop=True)
            cur = b.copy()
            frames.append(cur.copy())
            for k in order:
                cur[self.features[k]] = row[self.features[k]].iloc[0]
                frames.append(cur.copy())
            plan.append(order)
        p = self.model.predict_proba(pd.concat(frames, ignore_index=True))[:, 1].reshape(n_perm, F + 1, n_bg)
        for t, order in enumerate(plan):
            d = p[t, 1:, :] - p[t, :-1, :]          # marginal gain of each step, per background row
            contrib[order] += d.mean(axis=1)
        contrib = contrib / n_perm * 100.0
        total = float(np.abs(contrib).sum()) or 1.0
        out = []
        for col, d in zip(self.features, contrib):
            val = row[col].iloc[0]
            val = None if pd.isna(val) else (val.item() if hasattr(val, "item") else val)
            out.append({"factor": col, "label": self.label(col), "value_text": self.display(col, val), "value": val,
                        "contribution_pct_points": round(float(d), 2),
                        "share_pct": round(abs(float(d)) / total * 100.0, 1),
                        "direction": "increases" if d > 0.05 else "decreases" if d < -0.05 else "neutral"})
        out.sort(key=lambda r: -abs(r["contribution_pct_points"]))
        return out

    def _average_risk_pct(self) -> float:
        bg = self.artifact.get("background")
        if bg is None or len(bg) == 0:
            return round(float(self.model.predict_proba(pd.DataFrame([{c: self.baseline_value(c) for c in self.features}]))[:, 1][0]) * 100.0, 1)
        return round(float(self.model.predict_proba(bg[self.features])[:, 1].mean()) * 100.0, 1)

    def _explain_occlusion(self, row):
        p_full = float(self.model.predict_proba(row)[:, 1][0])
        variants = []
        for col in self.features:
            v = row.copy()
            v[col] = self.baseline_value(col)
            variants.append(v)
        probs = self.model.predict_proba(pd.concat(variants, ignore_index=True))[:, 1]
        deltas = (p_full - probs) * 100.0
        total = float(np.abs(deltas).sum()) or 1.0
        out = []
        for col, d in zip(self.features, deltas):
            out.append({"factor": col, "label": self.label(col), "value_text": self.display(col, None if pd.isna(row[col].iloc[0]) else (row[col].iloc[0].item() if hasattr(row[col].iloc[0], "item") else row[col].iloc[0])), "value": None if pd.isna(row[col].iloc[0]) else
                        (row[col].iloc[0].item() if hasattr(row[col].iloc[0], "item") else row[col].iloc[0]),
                        "contribution_pct_points": round(float(d), 2),
                        "share_pct": round(abs(float(d)) / total * 100.0, 1),
                        "direction": "increases" if d > 0.05 else "decreases" if d < -0.05 else "neutral"})
        out.sort(key=lambda r: -abs(r["contribution_pct_points"]))
        return out

    def predict_one(self, record: dict) -> dict:
        X, ignored, bad = self._prepare([record])
        flags = self._record_flags(X, bad)
        p = float(self.model.predict_proba(X)[:, 1][0])
        risk = round(p * 100.0, 1)
        factors = self.explain_one(X)
        return to_builtin({"risk_pct": risk, "probability": p, "stratum": self.band(risk),
                           "predicted_class": int(p >= self.threshold),
                           "baseline_risk_pct": self._average_risk_pct(),
                           "top_contributing_factors": factors[:5], "all_factors": factors,
                           "needs_review": flags[0]["needs_review"], "review_reasons": flags[0]["reasons"]})

    def form_schema(self) -> list[dict]:
        """Description of each input for the web form (no model internals)."""
        from .profiles import PROFILES, label_for
        profile = self.artifact.get("profile")
        meta_all = PROFILES.get(profile or "", {}).get("fields", {})
        out = []
        for col in self.features:
            ref, kind = self.reference[col], self.types[col]
            meta = meta_all.get(col, {})
            item = {"name": col, "label": label_for(profile, col), "unit": meta.get("unit"),
                    "group": meta.get("group", "Details"), "baseline": self.baseline_value(col)}
            opt_text = meta.get("options")
            if kind == "categorical":
                item.update(type="select", options=[{"value": v, "label": v} for v in sorted(ref["counts"])])
            elif ref["kind"] == "discrete" and len(ref["counts"]) <= 12:
                vals = sorted(ref["counts"], key=float)
                vals = [float(v) if "." in v else int(float(v)) for v in vals]
                item.update(type="select", options=[
                    {"value": v, "label": (opt_text or ({0: "No", 1: "Yes"} if set(vals) <= {0, 1} else {})).get(v, str(v))}
                    for v in vals])
            else:
                item.update(type="number", min=ref["min"], max=ref["max"])
            out.append(item)
        # Group order follows the profile (clinical groups first); fields keep the profile's order too.
        pos = {c: i for i, c in enumerate(meta_all)}
        order = list(dict.fromkeys([m.get("group", "Details") for m in meta_all.values()] +
                                   [meta_all.get(c, {}).get("group", "Details") for c in self.features]))
        out.sort(key=lambda f: (order.index(f["group"]), pos.get(f["name"], 999)))
        return to_builtin(out)

    def reliability(self, record: dict, history: list[dict]) -> dict:
        """Real checks only: this record against the training reference, plus rolling PSI/KS over the user's
        saved assessments (only when enough assessments exist for the monitor to be meaningful)."""
        X, _, bad = self._prepare([record])
        reasons = self._record_flags(X, bad)[0]["reasons"]
        out_range = [r for r in reasons if "outside training range" in r]
        unseen = [r for r in reasons if "never seen" in r]
        missing = [r for r in reasons if "missing" in r or "could not be interpreted" in r]
        checks = {"features_checked": len(self.features), "out_of_range": out_range, "unseen_values": unseen,
                  "missing_or_invalid": missing, "passed": not reasons}
        try:
            frame = pd.DataFrame(history)[self.features] if history else pd.DataFrame(columns=self.features)
            shift = self.monitor.compare(frame) if len(frame) else {
                "status": "INSUFFICIENT_DATA", "n_rows": 0, "min_batch": self.monitor.config.min_batch,
                "results": [], "message": "No saved assessments yet."}
        except Exception:  # noqa
            shift = {"status": "INSUFFICIENT_DATA", "n_rows": len(history), "min_batch": self.monitor.config.min_batch,
                     "results": [], "message": "Shift monitoring is unavailable."}
        slim = [{"feature": r["feature"], "label": self.label(r["feature"]), "psi": r.get("psi"),
                 "p_value": r.get("p_value"), "test": r.get("test"), "missing_delta": r.get("missing_delta"),
                 "unseen_rate": r.get("unseen_rate"), "severity": r.get("severity")} for r in shift.get("results", [])]
        shift = {k: v for k, v in shift.items() if k != "results"} | {"features": slim}
        return to_builtin({"record_checks": checks, "shift": shift})

    def model_info(self) -> dict:
        ta = self.artifact.get("trained_at") or ""
        return to_builtin({"version": f"BRISK2 · {ta[:10]}" if ta else "BRISK2",
                           "trained_at": ta, "decision_threshold_pct": round(self.threshold * 100, 1),
                           "bands": [{"name": "Low", "from": 0, "to": 20}, {"name": "Moderate", "from": 20, "to": 50},
                                     {"name": "High", "from": 50, "to": 100}]})

    def display(self, col: str, value) -> str:
        from .profiles import value_text
        return value_text(self.artifact.get("profile"), col, value)

    def label(self, col: str) -> str:
        from .profiles import label_for
        return label_for(self.artifact.get("profile"), col)
