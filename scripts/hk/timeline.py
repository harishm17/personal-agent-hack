"""Work out the day's milestones from the build start and the deadline.

  ./hk timeline --start 11:00 [--deadline 16:30] [--break "13:30 lunch"]... [--write]

Same-day events only. Prints the milestones and a CONTRACT.md timetable; --write also stores them in
.hk/config.json "timeline", which the clock hook shows to every agent.
Rules (shares are of the build window):
  +30 min (+60 when the window is over 12 hours)  contract frozen, fixtures committed, streams launched
  25%                                             first sync: real outputs replace fixtures
  40%                                             first end-to-end run; record a backup clip of it
  the earlier of 75% and deadline -90 min         feature freeze
  deadline -60 min                                code freeze: video and pitch rehearsal
  deadline -20 min                                first version of the form submitted
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import load_config, repo_root  # noqa: E402


def hhmm(value: str) -> int:
    hh, mm = value.strip().split(":")
    return int(hh) * 60 + int(mm)


def fmt(minutes: float) -> str:
    m = int(round(minutes / 5) * 5)
    return f"{m // 60:02d}:{m % 60:02d}"


def milestones(start: int, deadline: int) -> list[tuple[int, str]]:
    window = deadline - start
    kickoff = 60 if window > 12 * 60 else 30
    rows = [
        (start + kickoff, "contract frozen, fixtures committed, streams launched"),
        (start + 0.25 * window, "first sync: real outputs replace fixtures"),
        (start + 0.40 * window, "first end-to-end run with real inputs; record a backup clip"),
        (min(start + 0.75 * window, deadline - 90), "feature freeze"),
        (deadline - 60, "code freeze: record video, pitch rehearsal"),
        (deadline - 20, "first version of the form submitted (./hk submit passes)"),
        (deadline, "deadline"),
    ]
    return [(int(round(t / 5) * 5), label) for t, label in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, help="build start, HH:MM")
    ap.add_argument("--deadline", help="HH:MM; default is event.deadline in .hk/config.json")
    ap.add_argument("--break", dest="breaks", action="append", default=[], metavar='"HH:MM label"',
                    help="a fixed item such as lunch or judging; repeat for more")
    ap.add_argument("--write", action="store_true", help="store the timeline in .hk/config.json")
    args = ap.parse_args()
    root = repo_root()
    cfg = load_config(root)
    try:
        start = hhmm(args.start)
        deadline = hhmm(args.deadline or cfg.get("event", {}).get("deadline", ""))
        fixed = [(hhmm(b.split(None, 1)[0]), b.split(None, 1)[1]) for b in args.breaks]
    except (ValueError, IndexError):
        print('[hk] times are HH:MM; a break is "HH:MM label"')
        return 2
    if deadline - start < 120:
        print("[hk] the window is under two hours (or crosses midnight); write the timeline by hand")
        return 2
    rows = sorted(milestones(start, deadline) + fixed, key=lambda r: r[0])
    print(f"[hk] build window {fmt(start)} to {fmt(deadline)} ({(deadline - start) / 60:.1f} h)")
    print("| Time | Milestone |\n|---|---|")
    for t, label in rows:
        print(f"| {fmt(t)} | {label} |")
    if args.write:
        path = root / ".hk" / "config.json"
        data = json.loads(path.read_text())
        data["timeline"] = [[fmt(t), label] for t, label in rows]
        data.setdefault("event", {})["deadline"] = fmt(deadline)
        if not data["event"].get("date"):
            data["event"]["date"] = dt.date.today().isoformat()
        path.write_text(json.dumps(data, indent=2) + "\n")
        print("[hk] written to .hk/config.json; copy the table into CONTRACT.md \"Timetable\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
