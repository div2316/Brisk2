"""Password hashing (scrypt), input validation and a simple login throttle. Stdlib only."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import threading
import time

_N, _R, _P = 2 ** 14, 8, 1
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return "scrypt${}${}${}${}${}".format(_N, _R, _P, base64.b64encode(salt).decode(),
                                          base64.b64encode(digest).decode())


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, digest = stored.split("$")
        expected = base64.b64decode(digest)
        actual = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt),
                                n=int(n), r=int(r), p=int(p), dklen=len(expected))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def validate_email(email: str) -> str:
    email = (email or "").strip()
    if len(email) > 254 or not _EMAIL.match(email):
        raise ValueError("Enter a valid email address.")
    return email


def validate_password(password: str) -> str:
    if len(password or "") < 10:
        raise ValueError("Password must be at least 10 characters.")
    if len(password) > 128:
        raise ValueError("Password must be at most 128 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain at least one letter and one number.")
    return password


def validate_name(name: str) -> str:
    name = (name or "").strip()
    if not 1 <= len(name) <= 80:
        raise ValueError("Enter your name (up to 80 characters).")
    return name


class LoginThrottle:
    """Lock a key (email|ip) for `lock_seconds` after `max_failures` consecutive failures."""

    def __init__(self, max_failures: int = 5, lock_seconds: int = 900):
        self.max_failures, self.lock_seconds = max_failures, lock_seconds
        self._state: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str) -> int:
        with self._lock:
            count, until = self._state.get(key, (0, 0.0))
            remaining = until - time.time()
            if remaining > 0:
                return int(remaining) + 1
            if until and remaining <= 0:
                self._state.pop(key, None)
            return 0

    def failure(self, key: str):
        with self._lock:
            count, _ = self._state.get(key, (0, 0.0))
            count += 1
            until = time.time() + self.lock_seconds if count >= self.max_failures else 0.0
            self._state[key] = (count, until)

    def success(self, key: str):
        with self._lock:
            self._state.pop(key, None)
