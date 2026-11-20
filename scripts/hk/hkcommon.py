"""Shared helpers for the hackathon kit scripts: repo root, config, local state, clock."""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path


def git(args: list[str], cwd: Path | str, check: bool = False) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and out.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout


def repo_root(cwd: Path | str | None = None) -> Path:
    cwd = Path(cwd or os.getcwd())
    top = git(["rev-parse", "--show-toplevel"], cwd).strip()
    return Path(top) if top else cwd


def load_config(root: Path) -> dict:
    path = root / ".hk" / "config.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}


def state_dir(root: Path) -> Path:
    d = root / ".hk" / "state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def hooks_disabled() -> bool:
    return os.environ.get("HK_HOOKS", "").lower() in {"0", "off", "false", "no"}


def read_owns(root: Path) -> tuple[str, list[str]]:
    """Return (stream name, globs) for this checkout, or ("", []) when unrestricted."""
    path = state_dir(root) / "owns"
    if not path.exists():
        return "", []
    stream, globs = "", []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("stream:"):
            stream = line.split(":", 1)[1].strip()
        else:
            globs.append(line)
    return stream, globs


def _parse_hhmm(value: str, today: dt.date) -> dt.datetime | None:
    try:
        hh, mm = value.strip().split(":")
        return dt.datetime.combine(today, dt.time(int(hh), int(mm)))
    except (ValueError, AttributeError):
        return None


def _fmt_delta(delta: dt.timedelta) -> str:
    mins = int(delta.total_seconds() // 60)
    if mins < 0:
        return f"{-mins} min ago"
    h, m = divmod(mins, 60)
    return f"{h}h{m:02d}m" if h else f"{m} min"


def clock_line(cfg: dict, now: dt.datetime | None = None, verbose: bool = False) -> str:
    """One status line: time, deadline, next timeline item. Empty when no deadline is set."""
    now = now or dt.datetime.now()
    event = cfg.get("event", {})
    date_str = event.get("date") or ""
    try:
        day = dt.date.fromisoformat(date_str) if date_str else now.date()
    except ValueError:
        day = now.date()
    if day != now.date():
        return f"[hk] event date {day} (today is {now.date()}): clock paused"
    deadline = _parse_hhmm(event.get("deadline", ""), day)
    if not deadline:
        return ""
    left = deadline - now
    parts = [f"[hk] {now:%H:%M}", f"deadline {deadline:%H:%M}"]
    parts.append("PAST DEADLINE" if left.total_seconds() < 0 else f"{_fmt_delta(left)} left")
    upcoming = []
    for item in cfg.get("timeline", []):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        at = _parse_hhmm(item[0], day)
        if at and at >= now:
            upcoming.append((at, item[1]))
    upcoming.sort()
    if upcoming:
        at, label = upcoming[0]
        parts.append(f"next {at:%H:%M} {label} (in {_fmt_delta(at - now)})")
    line = " · ".join(parts)
    if 0 <= left.total_seconds() <= 30 * 60:
        line += " · FINAL 30 MIN: no new features, follow the hackathon-demo skill's Submission steps (./hk submit)"
    if verbose and len(upcoming) > 1:
        line += "\n[hk] later: " + "; ".join(f"{a:%H:%M} {l}" for a, l in upcoming[1:])
    return line
