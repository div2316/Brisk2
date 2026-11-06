"""Persistence layer (SQLAlchemy Core). PostgreSQL in Docker; SQLite works for local tests.

Tables: users, sessions, assessments, audit, password_resets.
Timestamps are stored as ISO-8601 UTC strings so the same SQL runs on both engines.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

_PK = {"postgresql": "SERIAL PRIMARY KEY", "sqlite": "INTEGER PRIMARY KEY AUTOINCREMENT"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id {pk},
  email TEXT NOT NULL,
  name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users(email);
CREATE TABLE IF NOT EXISTS sessions(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  csrf TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assessments(
  id {pk},
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  risk_pct REAL NOT NULL,
  stratum TEXT NOT NULL,
  payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_assess_user ON assessments(user_id, id);
CREATE TABLE IF NOT EXISTS audit(
  id {pk},
  user_id INTEGER,
  action TEXT NOT NULL,
  detail TEXT,
  created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS password_resets(
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL);
"""


class DuplicateEmail(Exception):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class Database:
    def __init__(self, url: str, wait_seconds: int = 60):
        if url.startswith("postgres://"):
            url = "postgresql+psycopg2://" + url[len("postgres://"):]
        elif url.startswith("postgresql://"):
            url = "postgresql+psycopg2://" + url[len("postgresql://"):]
        self.engine = create_engine(url, pool_pre_ping=True, future=True)
        self.dialect = self.engine.dialect.name
        deadline = time.time() + wait_seconds
        while True:  # the database container may still be starting
            try:
                self._create_schema()
                break
            except OperationalError:
                if time.time() > deadline:
                    raise
                time.sleep(2)

    def _create_schema(self):
        pk = _PK.get(self.dialect, _PK["sqlite"])
        with self.engine.begin() as c:
            if self.dialect == "sqlite":
                c.exec_driver_sql("PRAGMA foreign_keys=ON")
            for stmt in SCHEMA.format(pk=pk).split(";"):
                if stmt.strip():
                    c.execute(text(stmt))

    def _tx(self):
        return self.engine.begin()

    # -- users ---------------------------------------------------------------------
    def create_user(self, email: str, name: str, password_hash: str) -> int:
        try:
            with self._tx() as c:
                return c.execute(text(
                    "INSERT INTO users(email,name,password_hash,created_at) "
                    "VALUES(:e,:n,:p,:t) RETURNING id"),
                    {"e": email.strip().lower(), "n": name.strip(), "p": password_hash, "t": _iso(_now())}).scalar_one()
        except IntegrityError as exc:
            raise DuplicateEmail(email) from exc

    def get_user_by_email(self, email: str):
        with self._tx() as c:
            row = c.execute(text("SELECT * FROM users WHERE email=:e"), {"e": email.strip().lower()}).mappings().first()
        return dict(row) if row else None

    def set_password(self, user_id: int, password_hash: str):
        with self._tx() as c:
            c.execute(text("UPDATE users SET password_hash=:p WHERE id=:i"), {"p": password_hash, "i": user_id})
            c.execute(text("DELETE FROM sessions WHERE user_id=:i"), {"i": user_id})

    def delete_user(self, user_id: int):
        with self._tx() as c:
            for table in ("sessions", "assessments", "password_resets"):
                c.execute(text(f"DELETE FROM {table} WHERE user_id=:i"), {"i": user_id})
            c.execute(text("DELETE FROM audit WHERE user_id=:i"), {"i": user_id})
            c.execute(text("DELETE FROM users WHERE id=:i"), {"i": user_id})

    # -- sessions ------------------------------------------------------------------
    def create_session(self, user_id: int, days: int = 7) -> tuple[str, str]:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        now = _now()
        with self._tx() as c:
            c.execute(text("DELETE FROM sessions WHERE expires_at < :n"), {"n": _iso(now)})
            c.execute(text("INSERT INTO sessions(token_hash,user_id,csrf,created_at,expires_at) VALUES(:h,:u,:c,:a,:x)"),
                      {"h": _hash_token(token), "u": user_id, "c": csrf, "a": _iso(now),
                       "x": _iso(now + timedelta(days=days))})
        return token, csrf

    def get_session(self, token: str | None):
        if not token:
            return None
        with self._tx() as c:
            row = c.execute(text(
                "SELECT s.csrf, s.expires_at, u.id AS user_id, u.email, u.name FROM sessions s "
                "JOIN users u ON u.id=s.user_id WHERE s.token_hash=:h"), {"h": _hash_token(token)}).mappings().first()
        if not row or row["expires_at"] < _iso(_now()):
            return None
        return dict(row)

    def delete_session(self, token: str | None):
        if token:
            with self._tx() as c:
                c.execute(text("DELETE FROM sessions WHERE token_hash=:h"), {"h": _hash_token(token)})

    # -- password reset ------------------------------------------------------------
    def create_reset_token(self, user_id: int, minutes: int = 30) -> str:
        token = secrets.token_urlsafe(32)
        with self._tx() as c:
            c.execute(text("DELETE FROM password_resets WHERE user_id=:u"), {"u": user_id})
            c.execute(text("INSERT INTO password_resets(token_hash,user_id,expires_at) VALUES(:h,:u,:x)"),
                      {"h": _hash_token(token), "u": user_id, "x": _iso(_now() + timedelta(minutes=minutes))})
        return token

    def consume_reset_token(self, token: str):
        with self._tx() as c:
            row = c.execute(text("SELECT user_id, expires_at FROM password_resets WHERE token_hash=:h"),
                            {"h": _hash_token(token)}).mappings().first()
            if not row:
                return None
            c.execute(text("DELETE FROM password_resets WHERE token_hash=:h"), {"h": _hash_token(token)})
        return row["user_id"] if row["expires_at"] >= _iso(_now()) else None

    # -- assessments ---------------------------------------------------------------
    def add_assessment(self, user_id: int, risk_pct: float, stratum: str, payload: dict) -> int:
        with self._tx() as c:
            return c.execute(text(
                "INSERT INTO assessments(user_id,created_at,risk_pct,stratum,payload) "
                "VALUES(:u,:t,:r,:s,:p) RETURNING id"),
                {"u": user_id, "t": _iso(_now()), "r": risk_pct, "s": stratum, "p": json.dumps(payload)}).scalar_one()

    @staticmethod
    def _assessment(row) -> dict:
        out = dict(row)
        out["payload"] = json.loads(out["payload"])
        return out

    def list_assessments(self, user_id: int, limit: int = 50) -> list[dict]:
        with self._tx() as c:
            rows = c.execute(text(
                "SELECT id,created_at,risk_pct,stratum,payload FROM assessments WHERE user_id=:u "
                "ORDER BY id DESC LIMIT :l"), {"u": user_id, "l": limit}).mappings().all()
        out = []
        for r in rows:
            d = dict(r)
            try:
                d["needs_review"] = bool(json.loads(d.pop("payload"))["prediction"].get("needs_review"))
            except Exception:  # noqa
                d["needs_review"] = None
            out.append(d)
        return out

    def list_patients(self, user_id: int, limit: int = 2000) -> list[dict]:
        with self._tx() as c:
            rows = c.execute(text("SELECT payload FROM assessments WHERE user_id=:u ORDER BY id DESC LIMIT :l"),
                             {"u": user_id, "l": limit}).mappings().all()
        return [json.loads(r["payload"])["patient"] for r in rows]

    def latest_assessment(self, user_id: int):
        with self._tx() as c:
            row = c.execute(text("SELECT * FROM assessments WHERE user_id=:u ORDER BY id DESC LIMIT 1"),
                            {"u": user_id}).mappings().first()
        return self._assessment(row) if row else None

    def get_assessment(self, user_id: int, assessment_id: int):
        with self._tx() as c:
            row = c.execute(text("SELECT * FROM assessments WHERE id=:i AND user_id=:u"),
                            {"i": assessment_id, "u": user_id}).mappings().first()
        return self._assessment(row) if row else None

    def delete_assessments(self, user_id: int) -> int:
        with self._tx() as c:
            return c.execute(text("DELETE FROM assessments WHERE user_id=:u"), {"u": user_id}).rowcount

    # -- audit ---------------------------------------------------------------------
    def audit(self, user_id, action: str, detail: str | None = None):
        with self._tx() as c:
            c.execute(text("INSERT INTO audit(user_id,action,detail,created_at) VALUES(:u,:a,:d,:t)"),
                      {"u": user_id, "a": action, "d": detail, "t": _iso(_now())})

    def list_audit(self, user_id: int, limit: int = 50) -> list[dict]:
        with self._tx() as c:
            rows = c.execute(text("SELECT action,detail,created_at FROM audit WHERE user_id=:u "
                                  "ORDER BY id DESC LIMIT :l"), {"u": user_id, "l": limit}).mappings().all()
        return [dict(r) for r in rows]
