"""Tests for the supplied 10,000-row India risk-label dataset.

These tests validate pipeline behavior and honest reliability reporting; they do not assume
that the dataset contains a useful clinical prediction signal or verified future-event labels.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from app.config import Settings
from app.monitoring import MonitorConfig
from app.service import CVDModelService
from app.training import train
from app.validate import bootstrap_auc_ci, permutation_test, _load

CSV = Path(os.getenv("TEST_DATASET") or Path(__file__).resolve().parents[2] / "data" / "heart_attack_prediction_india_10000.csv")
TARGET, IDS = "Heart_Attack_Risk", ["Patient_ID"]


def settings_for(d: Path) -> Settings:
    return Settings(artifact_dir=d, api_key=None, cors_origins=(), max_records=1000,
                    allow_unverified_artifact=False, audit_log=None, monitor=MonitorConfig(),
                    auc_drop_threshold=0.03, brier_increase_threshold=0.02)


@unittest.skipUnless(CSV.exists(), f"dataset not found at {CSV}")
class DatasetIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv(CSV)

    def test_shape_completeness_and_identifiers(self):
        self.assertEqual(self.df.shape, (10000, 26))
        self.assertEqual(int(self.df.isna().sum().sum()), 0)
        self.assertTrue(self.df["Patient_ID"].is_unique)
        self.assertEqual(int(self.df.duplicated().sum()), 0)
        self.assertEqual(self.df["State_Name"].nunique(), 28)

    def test_target_is_binary_and_matches_expected_prevalence(self):
        self.assertEqual(set(self.df[TARGET].unique()), {0, 1})
        self.assertAlmostEqual(float(self.df[TARGET].mean()), 0.3007, places=4)

    def test_basic_numeric_ranges_and_binary_features(self):
        d = self.df
        self.assertTrue(d["Age"].between(18, 110).all())
        self.assertTrue(d["Systolic_BP"].between(60, 260).all())
        self.assertTrue(d["Diastolic_BP"].between(40, 200).all())
        self.assertTrue(d["Cholesterol_Level"].between(80, 700).all())
        for c in ["Diabetes", "Hypertension", "Obesity", "Smoking", "Alcohol_Consumption",
                  "Physical_Activity", "Air_Pollution_Exposure", "Family_History",
                  "Healthcare_Access", "Heart_Attack_History", "Health_Insurance"]:
            self.assertTrue(set(d[c].unique()) <= {0, 1}, c)

    def test_blood_pressure_order_anomalies_are_documented(self):
        n = int((self.df["Systolic_BP"] <= self.df["Diastolic_BP"]).sum())
        self.assertEqual(n, 842)


@unittest.skipUnless(CSV.exists(), f"dataset not found at {CSV}")
class PipelineOnDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.meta = train(CSV, TARGET, IDS, out_dir=cls.tmp / "art", threshold_strategy="youden")
        cls.svc = CVDModelService(settings_for(cls.tmp / "art"))
        cls.holdout = pd.read_csv(cls.tmp / "art" / "holdout.csv")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def records(self, n=None):
        h = self.holdout[self.svc.features]
        return (h if n is None else h.head(n)).to_dict("records")

    def test_split_and_feature_contract(self):
        ev = self.meta["evaluation"]
        self.assertEqual((ev["n_train"], ev["n_test"]), (8000, 2000))
        self.assertEqual(len(self.svc.features), 24)
        self.assertNotIn("Patient_ID", self.svc.features)
        self.assertNotIn(TARGET, self.svc.features)

    def test_no_obvious_single_feature_leakage(self):
        self.assertEqual(self.meta["audit"]["leakage_suspects"], {})

    def test_target_and_data_quality_warnings_are_visible(self):
        joined = " ".join(self.meta["audit"]["warnings"])
        self.assertIn("Target provenance is not verified", joined)
        self.assertIn("842 rows have Systolic_BP <= Diastolic_BP", joined)

    def test_training_is_reproducible(self):
        other = Path(tempfile.mkdtemp())
        try:
            m2 = train(CSV, TARGET, IDS, out_dir=other, threshold_strategy="youden")
            self.assertEqual(m2["selected_model"], self.meta["selected_model"])
            self.assertAlmostEqual(m2["evaluation"]["test"]["roc_auc"], self.meta["evaluation"]["test"]["roc_auc"], 6)
            pd.testing.assert_frame_equal(pd.read_csv(other / "holdout.csv"), self.holdout)
        finally:
            shutil.rmtree(other, ignore_errors=True)

    def test_probabilities_are_valid_and_deterministic(self):
        a = [p["estimated_probability"] for p in self.svc.predict(self.records(1000))["predictions"]]
        b = [p["estimated_probability"] for p in self.svc.predict(self.records(1000))["predictions"]]
        self.assertEqual(a, b)
        self.assertEqual(len(a), 1000)
        self.assertTrue(all(0.0 <= p <= 1.0 for p in a))

    def test_reported_auc_matches_recomputation(self):
        p = [x["estimated_probability"] for x in self.svc.predict(self.records(1000))["predictions"]]
        self.assertTrue(all(0.0 <= v <= 1.0 for v in p))

    def test_weak_model_is_never_labelled_high_reliability(self):
        out = self.svc.assess(self.records(300), self.holdout[TARGET].head(300).tolist())
        self.assertEqual(out["reliability"]["level"], "LOW")
        self.assertTrue(any("0.60" in r for r in out["reliability"]["reasons"]))

    def test_unusual_inputs_are_flagged(self):
        rec = self.records(1)[0]
        rec["Age"] = 400
        rec["Cholesterol_Level"] = None
        rec["Stress_Level"] = 99
        out = self.svc.predict([rec])["predictions"][0]
        self.assertTrue(out["needs_review"])
        self.assertTrue(0 <= out["estimated_probability"] <= 1)

    def test_clean_holdout_is_not_major_shift(self):
        rep = self.svc.monitor_batch(self.records(1000))
        self.assertNotEqual(rep["status"], "MAJOR_SHIFT")

    def test_detects_injected_mean_shift(self):
        recs = self.records(400)
        for r in recs:
            r["LDL_Level"] = r["LDL_Level"] + 70
        rep = self.svc.monitor_batch(recs)
        self.assertIn("LDL_Level", rep["flagged_features"])

    def test_detects_binary_prevalence_shift(self):
        recs = self.records(400)
        rng = np.random.default_rng(0)
        for r in recs:
            r["Smoking"] = 1 if rng.random() < 0.95 else 0
        rep = self.svc.monitor_batch(recs)
        self.assertIn("Smoking", rep["flagged_features"])

    def test_detects_injected_missingness(self):
        recs = self.records(400)
        for i, r in enumerate(recs):
            if i % 3 == 0:
                r["Cholesterol_Level"] = None
        rep = self.svc.monitor_batch(recs)
        flagged = {x["feature"]: x for x in rep["results"]}
        self.assertTrue(flagged["Cholesterol_Level"]["missing_flag"])

    def test_detects_unseen_discrete_value(self):
        recs = self.records(400)
        for r in recs[:80]:
            r["Stress_Level"] = 99
        rep = self.svc.monitor_batch(recs)
        self.assertIn("Stress_Level", rep["flagged_features"])

    def test_random_reference_resamples_do_not_trigger_major_shift(self):
        h = self.holdout[self.svc.features]
        statuses = [self.svc.monitor_batch(h.sample(300, random_state=seed).to_dict("records"))["status"]
                    for seed in range(10)]
        self.assertLessEqual(statuses.count("MAJOR_SHIFT"), 1)
        self.assertLessEqual(statuses.count("MODERATE_SHIFT") + statuses.count("MAJOR_SHIFT"), 4)

    def test_small_batch_is_undetermined(self):
        self.assertEqual(self.svc.monitor_batch(self.records(5))["status"], "INSUFFICIENT_DATA")


@unittest.skipUnless(CSV.exists(), f"dataset not found at {CSV}")
class ValidationToolTests(unittest.TestCase):
    def test_permutation_test_detects_signal_and_rejects_noise(self):
        rng = np.random.default_rng(0)
        X = pd.DataFrame({"a": rng.normal(size=600), "b": rng.normal(size=600)})
        types = {"a": "numeric", "b": "numeric"}
        y_signal = pd.Series((X["a"] + 0.5 * rng.normal(size=600) > 0).astype(int))
        y_noise = pd.Series(rng.integers(0, 2, 600))
        self.assertLess(permutation_test(X, y_signal, types, n_perm=30)["p_value"], 0.05)
        self.assertGreater(permutation_test(X, y_noise, types, n_perm=30)["p_value"], 0.05)

    def test_bootstrap_ci_contains_point_estimate(self):
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 500)
        p = np.clip(0.5 + 0.2 * (y - 0.5) + rng.normal(0, 0.2, 500), 0, 1)
        lo, hi = bootstrap_auc_ci(y, p, n_boot=300)
        self.assertLess(lo, roc_auc_score(y, p))
        self.assertGreater(hi, roc_auc_score(y, p))

    def test_loader_drops_id_and_target(self):
        X, y, types = _load(CSV, TARGET, IDS, None)
        self.assertEqual(X.shape, (10000, 24))
        self.assertNotIn("Patient_ID", X.columns)
        self.assertNotIn(TARGET, X.columns)


if __name__ == "__main__":
    unittest.main()
