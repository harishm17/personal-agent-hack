"""SessionStart / UserPromptSubmit hook: put the hackathon clock in front of the agent.

SessionStart prints the full orientation (clock, timeline, this checkout's stream).
UserPromptSubmit prints one short clock line so long sessions never lose track of time.
Plain stdout on these two events is added to Claude's context.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import clock_line, hooks_disabled, load_config, read_owns, repo_root  # noqa: E402


def main() -> int:
    if hooks_disabled():
        return 0
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data = {}
    root = repo_root(data.get("cwd"))
    cfg = load_config(root)
    event = data.get("hook_event_name", "SessionStart")

    if event == "UserPromptSubmit":
        line = clock_line(cfg)
        if line:
            print(line)
        return 0

    if not cfg.get("timeline") and not cfg.get("ownership"):
        print("[hk] Hackathon kit repo, not set up yet: use the hackathon-kickoff skill first.")
        return 0
    line = clock_line(cfg, verbose=True)
    stream, globs = read_owns(root)
    who = (f"This checkout is stream {stream}; you may edit only {', '.join(globs)} "
           f"(plus NOTES/, AGENTS.md). Use the hackathon-stream skill."
           if stream else "This checkout has no stream assignment (lead/integrator).")
    print("\n".join(x for x in [
        line,
        f"[hk] {who}",
        "[hk] CONTRACT.md is the source of truth for interfaces, ownership and the timetable; "
        "AGENTS.md holds the shared quirks log. Read both before acting.",
    ] if x))
    return 0


if __name__ == "__main__":
    sys.exit(main())
