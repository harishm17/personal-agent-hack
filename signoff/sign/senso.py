"""Senso text check of every sentence on the sheet. Not wired until SENSO_API_KEY is in the keys file.

Until then `checks()` says so plainly and `blocking()` is empty, so the signing flow does not depend on it."""
from __future__ import annotations

import threading

from signoff import config

_lock = threading.Lock()
_checks: list[dict] = []
BLOCKING = ("conflict", "unsupported")


def configured() -> bool:
    return config.have("SENSO_API_KEY")


def reset() -> None:
    with _lock:
        _checks.clear()


def set_checks(checks: list[dict]) -> None:
    with _lock:
        _checks[:] = checks


def checks() -> dict:
    with _lock:
        rows = list(_checks)
    return {"configured": configured(), "label": None if configured() else "Senso not connected: no verdicts yet",
            "checks": rows, "blocking": [c for c in rows if c.get("verdict") in BLOCKING]}


def blocking() -> list[dict]:
    return checks()["blocking"]
