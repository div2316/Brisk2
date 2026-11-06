"""Runtime configuration, read once from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .monitoring import MonitorConfig

BASE_DIR = Path(__file__).resolve().parent.parent


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a number") from exc


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer") from exc


@dataclass(frozen=True)
class Settings:
    artifact_dir: Path
    api_key: str | None
    cors_origins: tuple[str, ...]
    max_records: int
    allow_unverified_artifact: bool
    audit_log: Path | None
    monitor: MonitorConfig
    auc_drop_threshold: float
    brier_increase_threshold: float
    database_url: str = "sqlite:///data/brisk.db"
    cookie_secure: bool = False
    session_days: int = 7

    @property
    def artifact_path(self) -> Path:
        return self.artifact_dir / "cvd_model.joblib"


def get_settings() -> Settings:
    origins = tuple(o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip())
    audit = os.getenv("AUDIT_LOG")
    return Settings(
        artifact_dir=Path(os.getenv("ARTIFACT_DIR", BASE_DIR / "artifacts")),
        api_key=os.getenv("API_KEY") or None,
        cors_origins=origins,
        max_records=_int("MAX_RECORDS", 1000),
        allow_unverified_artifact=os.getenv("ALLOW_UNVERIFIED_ARTIFACT", "0") == "1",
        audit_log=Path(audit) if audit else None,
        monitor=MonitorConfig(
            psi_moderate=_float("PSI_MODERATE", 0.20),
            psi_major=_float("PSI_MAJOR", 0.50),
            alpha=_float("KS_ALPHA", 0.05),
            min_effect=_float("MIN_EFFECT_SIZE", 0.10),
            missing_delta=_float("MISSING_DELTA", 0.05),
            min_batch=_int("MIN_MONITOR_BATCH", 300),
        ),
        auc_drop_threshold=_float("AUC_DROP_THRESHOLD", 0.03),
        brier_increase_threshold=_float("BRIER_INCREASE_THRESHOLD", 0.02),
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'brisk.db'}"),
        cookie_secure=os.getenv("COOKIE_SECURE", "0") == "1",
        session_days=_int("SESSION_DAYS", 7),
    )
