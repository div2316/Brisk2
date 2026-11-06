from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np


def to_builtin(obj):
    """Recursively convert numpy/pandas scalars to JSON-safe builtins (NaN/inf -> None)."""
    if isinstance(obj, dict):
        return {str(k): to_builtin(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_builtin(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return to_builtin(obj.tolist())
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        value = float(obj)
        return value if math.isfinite(value) else None
    if obj is None or isinstance(obj, str):
        return obj
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
