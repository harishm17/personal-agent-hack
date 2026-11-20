"""Print the clock, every stream's last activity, the gate state and open cross-check items."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import clock_line, git, load_config, read_owns, repo_root, state_dir  # noqa: E402


def main() -> int:
    root = repo_root()
    cfg = load_config(root)
    print(clock_line(cfg, verbose=True) or "[hk] no deadline set (.hk/config.json event.deadline)")
    stream, _ = read_owns(root)
    print(f"[hk] this checkout: {'stream ' + stream if stream else 'unrestricted (lead/integrator)'}")
    heads = [l for l in git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], root).split() if l]
    for name, paths in cfg.get("ownership", {}).items():
        pathspecs = [p.rstrip("*").rstrip("/") or "." for p in paths]
        last = git(["log", "-1", "--format=%cr · %s", *heads, "--", *pathspecs], root).strip() if heads else ""
        print(f"  {name:<12} {', '.join(paths):<30} last commit: {last or 'none yet'}")
    green = state_dir(root) / "last-green.json"
    fails = state_dir(root) / "gate-fails"
    if green.exists():
        print(f"[hk] gate: last green at HEAD {json.loads(green.read_text()).get('head', '')[:7]}"
              f"{'; consecutive fails ' + fails.read_text().strip() if fails.exists() and fails.read_text().strip() not in ('', '0') else ''}")
    notes = root / "NOTES" / "crosscheck.md"
    if notes.exists():
        open_items = [l for l in notes.read_text().splitlines() if l.startswith("- [ ]")]
        print(f"[hk] cross-check: {len(open_items)} open HIGH item(s) in NOTES/crosscheck.md")
    wt = subprocess.run(["git", "worktree", "list"], cwd=root, capture_output=True, text=True).stdout.strip()
    if wt.count("\n"):
        print("[hk] worktrees:\n" + "\n".join("  " + l for l in wt.splitlines()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
