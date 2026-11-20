"""PreToolUse hook: deny Edit/Write outside the paths this checkout's stream owns.

Ownership for a checkout lives in .hk/state/owns (untracked, per worktree), written by
`./hk own <STREAM>`. No file means unrestricted (lead / integrator).
Bash writes are not intercepted; this guards the common path, it is not a sandbox.
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import hooks_disabled, load_config, read_owns, repo_root  # noqa: E402

ALWAYS_ALLOWED = ["NOTES/*", "AGENTS.md", ".hk/state/*"]


def owner_of(rel: str, ownership: dict) -> str:
    for name, globs in ownership.items():
        if any(fnmatch.fnmatch(rel, g) for g in globs):
            return name
    return ""


def main() -> int:
    if hooks_disabled():
        return 0
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0
    tool_input = data.get("tool_input") or {}
    target = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not target:
        return 0
    root = repo_root(data.get("cwd"))
    stream, globs = read_owns(root)
    if not stream:
        return 0
    try:
        rel = Path(target).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return 0  # outside the repo: not ours to police
    if any(fnmatch.fnmatch(rel, g) for g in globs + ALWAYS_ALLOWED):
        return 0
    owner = owner_of(rel, load_config(root).get("ownership", {})) or "the integrator"
    notes = f"NOTES/{owner}.md" if owner != "the integrator" else "NOTES/INTEGRATOR.md"
    reason = (
        f"{rel} is owned by {owner}, not by stream {stream} (you own: {', '.join(globs)}). "
        f"Do not edit it. Append the exact change you need (file, line, replacement, why) to {notes} "
        f"and tell the human so they can relay it. If the human explicitly reassigns this path to you, "
        f"they run `./hk own {stream} --add '{rel}'` first."
    )
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
