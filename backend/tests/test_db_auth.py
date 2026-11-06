import tempfile
import time
import unittest
from pathlib import Path

from app.auth import (LoginThrottle, hash_password, validate_email, validate_password, verify_password)
from app.db import Database, DuplicateEmail


class AuthTests(unittest.TestCase):
    def test_hash_roundtrip(self):
        h = hash_password("correct horse 1")
        self.assertTrue(verify_password("correct horse 1", h))
        self.assertFalse(verify_password("wrong", h))
        self.assertFalse(verify_password("x", "garbage"))
        self.assertNotEqual(h, hash_password("correct horse 1"))

    def test_validation(self):
        with self.assertRaises(ValueError):
            validate_password("short1")
        with self.assertRaises(ValueError):
            validate_password("onlyletterslong")
        with self.assertRaises(ValueError):
            validate_email("nope")
        self.assertEqual(validate_email(" a@b.co "), "a@b.co")

    def test_throttle(self):
        t = LoginThrottle(max_failures=3, lock_seconds=1)
        for _ in range(3):
            self.assertEqual(t.blocked("k"), 0)
            t.failure("k")
        self.assertGreater(t.blocked("k"), 0)
        time.sleep(1.1)
        self.assertEqual(t.blocked("k"), 0)
        t.failure("k"); t.success("k")
        self.assertEqual(t.blocked("k"), 0)


class DbTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = Database(f"sqlite:///{Path(self.dir.name) / 't.db'}")

    def tearDown(self):
        self.dir.cleanup()

    def test_users_sessions(self):
        uid = self.db.create_user("A@x.com", "Ann", "h")
        with self.assertRaises(DuplicateEmail):
            self.db.create_user("a@X.com", "Dup", "h")
        self.assertEqual(self.db.get_user_by_email("a@x.com")["id"], uid)
        token, csrf = self.db.create_session(uid)
        s = self.db.get_session(token)
        self.assertEqual(s["csrf"], csrf)
        self.assertIsNone(self.db.get_session("bad"))
        self.assertIsNone(self.db.get_session(None))
        self.db.delete_session(token)
        self.assertIsNone(self.db.get_session(token))

    def test_expired_session(self):
        uid = self.db.create_user("b@x.com", "Bob", "h")
        token, _ = self.db.create_session(uid, days=-1)
        self.assertIsNone(self.db.get_session(token))

    def test_assessments_scoped_and_cascade(self):
        a = self.db.create_user("a@x.com", "A", "h")
        b = self.db.create_user("b@x.com", "B", "h")
        i = self.db.add_assessment(a, 41.5, "Moderate", {"patient": {"age": 5}, "prediction": {}})
        self.db.add_assessment(a, 70.0, "High", {"patient": {}, "prediction": {}})
        self.assertEqual(len(self.db.list_assessments(a)), 2)
        self.assertIsNone(self.db.get_assessment(b, i))
        self.assertEqual(self.db.get_assessment(a, i)["payload"]["patient"]["age"], 5)
        self.assertEqual(self.db.latest_assessment(a)["risk_pct"], 70.0)
        self.assertEqual(self.db.delete_assessments(a), 2)
        self.db.add_assessment(a, 10.0, "Low", {"patient": {}, "prediction": {}})
        self.db.delete_user(a)
        self.assertEqual(len(self.db.list_assessments(a)), 0)

    def test_audit(self):
        a = self.db.create_user("a@x.com", "A", "h")
        self.db.audit(a, "login")
        self.assertEqual(self.db.list_audit(a)[0]["action"], "login")


if __name__ == "__main__":
    unittest.main()
