"""Stop hook (and `./hk check`): run the repo's checks before an agent may end its turn.

- Runs only when the working tree or HEAD changed since the last green run.
- Checks come from .hk/config.json "checks": a path-prefix check ("web/": "...") runs when files under
  that prefix changed; "default" runs every time the gate runs.
- On failure it blocks the stop with the failing command and the tail of its output.
- After max_consecutive_fails failures in a row on a continued turn it lets the agent stop
  with a warning instead of looping. HK_HOOKS=off or "gate": {"enabled": false} disables it.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import git, hooks_disabled, load_config, repo_root, state_dir  # noqa: E402


def fingerprint(root: Path) -> tuple[str, str]:
    head = git(["rev-parse", "HEAD"], root).strip()
    h = hashlib.sha1(head.encode())
    h.update(git(["diff", "HEAD"], root).encode(errors="replace"))
    for rel in sorted(git(["ls-files", "--others", "--exclude-standard"], root).splitlines()):
        p = root / rel
        try:
            st = p.stat()
            h.update(f"{rel}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            pass
    return head, h.hexdigest()


def changed_paths(root: Path, last_head: str) -> list[str]:
    paths = set(git(["diff", "--name-only", "HEAD"], root).split())
    paths |= set(git(["ls-files", "--others", "--exclude-standard"], root).split())
    if last_head:
        paths |= set(git(["diff", "--name-only", last_head, "HEAD"], root).split())
    return sorted(p for p in paths if not p.startswith(".hk/state/"))


def select_checks(checks: dict, paths: list[str], run_all: bool) -> list[tuple[str, str]]:
    prefixed = {k: v for k, v in checks.items() if k != "default" and v}
    chosen = [(k, v) for k, v in prefixed.items() if run_all or any(p.startswith(k) for p in paths)]
    default = checks.get("default")
    if default:  # whole-repo check: runs whenever the gate runs
        chosen.append(("default", default))
    return chosen


def run_check(cmd: str, root: Path, timeout: int) -> tuple[int, str]:
    env = dict(os.environ, HK_HOOKS="off", CI="1")
    try:
        p = subprocess.run(["bash", "-lc", cmd], cwd=root, capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, (p.stdout + p.stderr)
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"") + (e.stderr or b"")
        if isinstance(out, bytes):
            out = out.decode(errors="replace")
        return 124, out + f"\n[hk] timed out after {timeout}s"


def tail(text: str, lines: int = 40) -> str:
    return "\n".join(text.rstrip().splitlines()[-lines:])


def main() -> int:
    manual = "--manual" in sys.argv
    run_all = "--all" in sys.argv
    if hooks_disabled() and not manual:
        return 0
    data = {}
    if not manual:
        try:
            data = json.load(sys.stdin)
        except json.JSONDecodeError:
            data = {}
        if data.get("background_tasks"):
            return 0  # paused on background work, not finished
    root = repo_root(data.get("cwd"))
    cfg = load_config(root)
    gate = cfg.get("gate", {})
    if not gate.get("enabled", True) and not manual:
        return 0
    st = state_dir(root)
    green_file, fails_file = st / "last-green.json", st / "gate-fails"
    last = json.loads(green_file.read_text()) if green_file.exists() else {}
    head, fp = fingerprint(root)
    if not manual and last.get("fingerprint") == fp:
        return 0
    checks = select_checks(cfg.get("checks", {}), changed_paths(root, last.get("head", "")), run_all or manual)
    if not checks:
        if manual:
            print("[hk] no checks configured in .hk/config.json \"checks\"")
        green_file.write_text(json.dumps({"head": head, "fingerprint": fp}))
        return 0
    timeout = int(gate.get("timeout_s", 300))
    for key, cmd in checks:
        code, out = run_check(cmd, root, timeout)
        if manual:
            print(f"[hk] {'PASS' if code == 0 else 'FAIL'} ({key}) {cmd}")
            if code:
                print(tail(out))
        if code != 0:
            fails = int(fails_file.read_text() or 0) + 1 if fails_file.exists() else 1
            fails_file.write_text(str(fails))
            if manual:
                return 1
            limit = int(gate.get("max_consecutive_fails", 3))
            if data.get("stop_hook_active") and fails > limit:
                fails_file.write_text("0")
                print(json.dumps({"systemMessage":
                    f"[hk] gate still failing after {limit} tries ({cmd}); letting the agent stop. "
                    "The build is red: fix it or hand it to the owner before the next sync point."}))
                return 0
            reason = (f"[hk gate] `{cmd}` exited {code}. Fix the root cause (do not skip, weaken or delete "
                      f"the check), rerun it, then finish. If the failure is in a path another stream owns, "
                      f"note it in NOTES/<owner>.md and say so. Last output:\n{tail(out)}")
            if data.get("hook_event_name") == "TaskCompleted":
                print(reason, file=sys.stderr)  # TaskCompleted blocks on exit 2, not JSON
                return 2
            print(json.dumps({"decision": "block", "reason": reason}))
            return 0
    fails_file.write_text("0")
    green_file.write_text(json.dumps({"head": head, "fingerprint": fp}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
