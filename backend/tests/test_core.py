import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from app.cli import make_demo_data
from app.config import Settings
from app.monitoring import MonitorConfig, ShiftMonitor, build_reference, psi_from_props
from app.preprocessing import coerce_frame, infer_feature_types
from app.reliability import combine, model_quality
from app.service import ArtifactError, CVDModelService
from app.training import encode_target, train
from app.utils import to_builtin


def settings_for(d: Path) -> Settings:
    return Settings(artifact_dir=d, api_key=None, cors_origins=(), max_records=1000,
                    allow_unverified_artifact=False, audit_log=None, monitor=MonitorConfig(min_batch=100),
                    auc_drop_threshold=0.03, brier_increase_threshold=0.02)


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.X = pd.DataFrame({"x": rng.normal(0, 1, 2000), "flag": rng.integers(0, 2, 2000).astype(float),
                               "cat": rng.choice(["a", "b", "c"], 2000)})
        self.types = infer_feature_types(self.X)
        self.ref = build_reference(self.X, self.types)
        self.mon = ShiftMonitor(self.ref)

    def test_psi_zero_for_identical(self):
        self.assertAlmostEqual(psi_from_props([.5, .5], [.5, .5]), 0.0)

    def test_binary_numeric_is_discrete(self):
        self.assertEqual(self.ref["flag"]["kind"], "discrete")

    def test_no_shift_on_same_distribution(self):
        rng = np.random.default_rng(2)
        cur = pd.DataFrame({"x": rng.normal(0, 1, 500), "flag": rng.integers(0, 2, 500).astype(float),
                            "cat": rng.choice(["a", "b", "c"], 500)})
        self.assertEqual(self.mon.compare(cur)["status"], "NO_SHIFT_DETECTED")

    def test_detects_mean_shift_and_binary_shift(self):
        rng = np.random.default_rng(3)
        cur = pd.DataFrame({"x": rng.normal(1.5, 1, 500), "flag": (rng.random(500) < 0.9).astype(float),
                            "cat": rng.choice(["a", "b", "c"], 500)})
        rep = self.mon.compare(cur)
        self.assertEqual(rep["status"], "MAJOR_SHIFT")
        self.assertIn("x", rep["flagged_features"])
        self.assertIn("flag", rep["flagged_features"])

    def test_missingness_and_unseen_category(self):
        rng = np.random.default_rng(4)
        cur = self.X.sample(500, random_state=1).reset_index(drop=True)
        cur.loc[rng.random(500) < 0.3, "x"] = np.nan
        cur.loc[:60, "cat"] = "zzz"
        rep = self.mon.compare(cur)
        flagged = {r["feature"]: r for r in rep["results"]}
        self.assertTrue(flagged["x"]["missing_flag"])
        self.assertTrue(flagged["cat"]["unseen_flag"])

    def test_small_batch_insufficient(self):
        self.assertEqual(self.mon.compare(self.X.head(5))["status"], "INSUFFICIENT_DATA")


class PreprocessingTests(unittest.TestCase):
    def test_coerce_flags_bad_values(self):
        X = pd.DataFrame({"a": [1, "abc", None, float("inf")], "b": ["x", " ", None, 3]})
        clean, bad = coerce_frame(X, {"a": "numeric", "b": "categorical"})
        self.assertEqual(bad["a"].tolist(), [False, True, False, True])
        self.assertTrue(clean["a"].isna().tolist()[1:])
        self.assertEqual(clean["b"].tolist()[0], "x")
        self.assertTrue(pd.isna(clean["b"].iloc[1]))

    def test_encode_target(self):
        self.assertEqual(encode_target(pd.Series([0, 1, 1])).tolist(), [0, 1, 1])
        with self.assertRaises(ValueError):
            encode_target(pd.Series([0, 1, 2]))
        self.assertEqual(encode_target(pd.Series(["yes", "no"]), "yes").tolist(), [1, 0])

    def test_to_builtin(self):
        out = to_builtin({"a": np.float64("nan"), "b": np.int64(3), "c": [np.bool_(True)]})
        self.assertEqual(out, {"a": None, "b": 3, "c": [True]})


class ReliabilityTests(unittest.TestCase):
    def test_levels(self):
        q = model_quality({"roc_auc": 0.8})
        ok = {"status": "NO_SHIFT_DETECTED", "flagged_features": [], "message": ""}
        self.assertEqual(combine(q, ok, 0, 100, None)["level"], "HIGH")
        major = {**ok, "status": "MAJOR_SHIFT", "flagged_features": ["x"]}
        self.assertEqual(combine(q, major, 0, 100, None)["level"], "LOW")
        small = {**ok, "status": "INSUFFICIENT_DATA", "message": "small"}
        self.assertEqual(combine(q, small, 0, 1, None)["level"], "UNDETERMINED")
        self.assertEqual(combine(model_quality({"roc_auc": 0.55}), ok, 0, 100, None)["level"], "LOW")


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        make_demo_data(cls.tmp / "demo.csv", n=1200)
        train(cls.tmp / "demo.csv", "target", ["patient_id"], out_dir=cls.tmp / "art")
        cls.svc = CVDModelService(settings_for(cls.tmp / "art"))
        cls.holdout = pd.read_csv(cls.tmp / "art" / "holdout.csv")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def records(self, n):
        return self.holdout[self.svc.features].head(n).to_dict("records")

    def test_predict_single_with_missing_and_unusual(self):
        rec = self.records(1)[0]
        rec["cholesterol"] = None
        rec["age"] = 400
        rec["smoking_status"] = "vapes"
        out = self.svc.predict([rec])["predictions"][0]
        self.assertTrue(0 <= out["estimated_probability"] <= 1)
        self.assertTrue(out["needs_review"])
        self.assertGreaterEqual(len(out["review_reasons"]), 2)

    def test_missing_column_rejected(self):
        rec = self.records(1)[0]; del rec["age"]
        with self.assertRaises(ValueError):
            self.svc.predict([rec])

    def test_assess_clean_batch_not_low(self):
        out = self.svc.assess(self.records(300), self.holdout["target"].head(300).tolist())
        self.assertNotEqual(out["shift_report"]["status"], "MAJOR_SHIFT")
        self.assertTrue(out["reliability"]["labelled_check_performed"])

    def test_assess_shifted_batch_flags(self):
        recs = self.records(300)
        for r in recs:
            r["cholesterol"] = (r["cholesterol"] or 240) + 120
        out = self.svc.assess(recs)
        self.assertIn(out["reliability"]["level"], ("CAUTION", "LOW"))
        self.assertIn("cholesterol", out["shift_report"]["flagged_features"])

    def test_assess_single_record_undetermined(self):
        out = self.svc.assess(self.records(1))
        self.assertEqual(out["shift_report"]["status"], "INSUFFICIENT_DATA")

    def test_bad_labels(self):
        with self.assertRaises(ValueError):
            self.svc.assess(self.records(40), [1, 0])
        with self.assertRaises(ValueError):
            self.svc.assess(self.records(2), [1, 2])

    def test_checksum_tamper_detected(self):
        d = self.tmp / "tamper"; shutil.copytree(self.tmp / "art", d)
        with open(d / "cvd_model.joblib", "ab") as fh:
            fh.write(b"x")
        with self.assertRaises(ArtifactError):
            CVDModelService(settings_for(d))

    def test_json_safe(self):
        import json
        json.dumps(self.svc.assess(self.records(100)), allow_nan=False)
        json.dumps(self.svc.metadata(), allow_nan=False)


@unittest.skipUnless(__import__("importlib").util.find_spec("fastapi")
                     and __import__("importlib").util.find_spec("httpx"), "fastapi/httpx not installed")
class ApiTests(unittest.TestCase):
    def test_web_flow(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        tmp = Path(tempfile.mkdtemp())
        try:
            make_demo_data(tmp / "demo.csv", n=900)
            train(tmp / "demo.csv", "target", ["patient_id"], out_dir=tmp / "a")
            s = Settings(**{**settings_for(tmp / "a").__dict__, "api_key": "secret",
                            "database_url": f"sqlite:///{tmp / 't.db'}"})
            holdout = pd.read_csv(tmp / "a" / "holdout.csv")
            feats = [c for c in holdout.columns if c != "target"]
            recs = holdout[feats].head(40).astype(object).where(holdout[feats].head(40).notna(), None).to_dict("records")
            with TestClient(create_app(s)) as c:
                self.assertEqual(c.get("/health").status_code, 200)
                self.assertEqual(c.get("/api/health").json()["model_loaded"], True)
                # machine API key auth
                self.assertEqual(c.get("/v1/schema").status_code, 401)
                self.assertEqual(c.get("/v1/schema", headers={"X-API-Key": "secret"}).status_code, 200)
                self.assertEqual(c.post("/v1/predict", json={"records": []},
                                        headers={"X-API-Key": "secret"}).status_code, 422)
                # web session flow
                self.assertIsNone(c.get("/api/auth/me").json()["user"])
                self.assertEqual(c.get("/api/schema").status_code, 401)
                body = {"name": "Ann", "email": "ann@example.com", "password": "longpass123", "accept_terms": True}
                self.assertEqual(c.post("/api/auth/signup", json=body).status_code, 201)
                self.assertEqual(c.post("/api/auth/signup", json=body).status_code, 409)
                self.assertEqual(c.post("/api/auth/login", json={"email": "ann@example.com", "password": "bad"}).status_code, 401)
                self.assertEqual(c.post("/api/auth/login", json=body).status_code, 200)
                self.assertEqual(c.get("/api/auth/me").json()["user"]["name"], "Ann")
                # CSRF enforced
                full = holdout[feats].dropna().iloc[0].to_dict()
                full = {k: (v.item() if hasattr(v, "item") else v) for k, v in full.items()}
                self.assertEqual(c.post("/api/predict", json=full).status_code, 403)
                h = {"X-CSRF-Token": c.cookies.get("cvd_csrf")}
                r = c.post("/api/predict", json=full, headers=h)
                self.assertEqual(r.status_code, 200, r.text)
                out = r.json()
                self.assertTrue(0 <= out["risk_pct"] <= 100)
                self.assertIn(out["stratum"], ("Low", "Moderate", "High"))
                self.assertEqual(len(out["top_contributing_factors"]), 5)
                self.assertEqual(len(c.get("/api/schema").json()["fields"]), len(feats))
                self.assertEqual(c.get("/api/patient").json()["id"], out["id"])
                self.assertEqual(len(c.get("/api/assessments").json()["items"]), 1)
                rep = c.get(f"/api/report/{out['id']}.pdf")
                self.assertEqual(rep.status_code, 200)
                self.assertTrue(rep.content.startswith(b"%PDF"))
                self.assertEqual(c.get("/api/report/9999.pdf").status_code, 404)
                bad = dict(full); bad.pop(feats[0])
                self.assertEqual(c.post("/api/predict", json=bad, headers=h).status_code, 422)
                self.assertEqual(c.delete("/api/patient", headers=h).json()["deleted"], 1)
                self.assertEqual(c.delete("/api/account", headers=h).status_code, 200)
                self.assertIsNone(c.get("/api/auth/me").json()["user"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
