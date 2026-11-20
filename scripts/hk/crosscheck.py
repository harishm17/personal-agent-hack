"""Cross-check new commits against CONTRACT.md with a second reviewer (ideally another model family).

  ./hk crosscheck once [--rev A..B | --commit SHA ...] [--backend codex|claude|cmd:'<shell>'] [--dry-run]
  ./hk crosscheck watch [--interval 90] [--until HH:MM] [--max-reviews 40] [--check-existing]

Backends (config "crosscheck.backend", default auto = codex if installed, else claude):
  codex   `codex exec` read-only, ephemeral (OpenAI model: a different family from Claude)
  claude  `claude -p --model sonnet` with hooks off (fresh context, same family)
  cmd:... any shell command that reads the prompt on stdin and prints the review
watch follows every local branch (worktrees share refs) and reviews each new non-merge commit once.
Reports: .hk/state/crosscheck/<time>-<label>.md; HIGH findings are appended to NOTES/crosscheck.md.
Stdout lines: XCHECK start|HIGH|done|error ...
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import git, load_config, repo_root, state_dir  # noqa: E402

MAX_DIFF_CHARS = 60_000

PROMPT = """You are an independent reviewer at a timed hackathon. Several coding agents work in parallel;
the contract below is the source of truth for interfaces, file formats and ownership.

Review ONLY the commit(s) below. Report real defects: contract violations (field names, shapes, event types,
endpoints), code that cannot work, tests or checks that were weakened to pass, faked or hardcoded results
presented as real, secrets in code, and edits to paths the author does not own. Ignore style.

Reply with JSON only, no prose, in this shape:
{{"findings": [{{"severity": "high|medium|low", "file": "path", "line": 0, "owner": "stream or empty",
"summary": "one sentence", "fix": "one sentence"}}]}}
Use "high" only for things that will break the demo or misrepresent results. Empty list if nothing is wrong.

=== CONTRACT.md ===
{contract}

=== COMMITS ===
{commits}
"""


def pick_backend(name: str) -> str:
    if name and name != "auto":
        return name
    return "codex" if shutil.which("codex") else "claude"


def run_backend(backend: str, prompt: str, root: Path, timeout: int = 900) -> str:
    env = dict(os.environ, HK_HOOKS="off")
    if backend == "codex":
        with tempfile.NamedTemporaryFile("r", suffix=".txt", delete=False) as out:
            out_path = out.name
        cmd = ["codex", "exec", "--sandbox", "read-only", "--ephemeral", "--skip-git-repo-check",
               "-C", str(root), "-o", out_path, "-"]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, env=env)
        text = Path(out_path).read_text() if Path(out_path).exists() else ""
        os.unlink(out_path)
        if p.returncode != 0 and not text:
            raise RuntimeError(f"codex exited {p.returncode}: {p.stderr[-500:]}")
        return text
    if backend == "claude":
        cmd = ["claude", "-p", "--model", "sonnet", "--output-format", "text",
               "--permission-mode", "dontAsk", "--allowedTools", "Read,Grep,Glob"]
        p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout,
                           env=env, cwd=root)
        if p.returncode != 0:
            raise RuntimeError(f"claude exited {p.returncode}: {p.stderr[-500:]}")
        return p.stdout
    if backend.startswith("cmd:"):
        p = subprocess.run(["bash", "-lc", backend[4:]], input=prompt, capture_output=True, text=True,
                           timeout=timeout, env=env, cwd=root)
        if p.returncode != 0:
            raise RuntimeError(f"command exited {p.returncode}: {p.stderr[-500:]}")
        return p.stdout
    raise ValueError(f"unknown backend {backend!r}")


def parse_findings(text: str) -> list[dict]:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return []
    try:
        return list(json.loads(match.group(0)).get("findings", []))
    except (json.JSONDecodeError, AttributeError):
        return []


def commits_text(root: Path, shas: list[str]) -> str:
    parts = []
    for sha in shas:
        parts.append(git(["show", "--stat", "--patch", "--format=commit %H%nAuthor: %an%nDate: %ci%n%n%B", sha], root))
    text = "\n".join(parts)
    if len(text) > MAX_DIFF_CHARS:
        text = text[:MAX_DIFF_CHARS] + f"\n[... truncated at {MAX_DIFF_CHARS} chars ...]"
    return text


def review(root: Path, shas: list[str], backend: str, label: str, dry_run: bool) -> list[dict]:
    contract_path = root / "CONTRACT.md"
    contract = contract_path.read_text() if contract_path.exists() else "(no CONTRACT.md)"
    prompt = PROMPT.format(contract=contract, commits=commits_text(root, shas))
    print(f"XCHECK start {label} commits={len(shas)} backend={backend}", flush=True)
    if dry_run:
        print(prompt)
        return []
    started = time.time()
    raw = run_backend(backend, prompt, root)
    findings = parse_findings(raw)
    out_dir = state_dir(root) / "crosscheck"
    out_dir.mkdir(exist_ok=True)
    stamp = dt.datetime.now().strftime("%H%M%S")
    report = out_dir / f"{stamp}-{label}.md"
    lines = [f"# Cross-check {label} ({backend}, {time.time() - started:.0f}s)", ""]
    lines += [f"- **{f.get('severity', '?').upper()}** `{f.get('file', '')}:{f.get('line', '')}` "
              f"[{f.get('owner', '')}] {f.get('summary', '')} Fix: {f.get('fix', '')}" for f in findings]
    if not findings:
        lines.append("No findings." if raw.strip() else "Reviewer returned nothing.")
    lines += ["", "<details><summary>raw</summary>", "", raw, "", "</details>"]
    report.write_text("\n".join(lines))
    highs = [f for f in findings if str(f.get("severity", "")).lower() == "high"]
    for f in highs:
        print(f"XCHECK HIGH {f.get('owner', '')} {f.get('file', '')}:{f.get('line', '')} {f.get('summary', '')}", flush=True)
    if highs:
        notes = root / "NOTES" / "crosscheck.md"
        notes.parent.mkdir(exist_ok=True)
        with notes.open("a") as fh:
            fh.write(f"\n## {dt.datetime.now():%H:%M} {label}\n")
            for f in highs:
                fh.write(f"- [ ] {f.get('owner', '')} `{f.get('file', '')}:{f.get('line', '')}` "
                         f"{f.get('summary', '')} Fix: {f.get('fix', '')}\n")
    counts = {s: sum(1 for f in findings if str(f.get("severity", "")).lower() == s) for s in ("high", "medium", "low")}
    print(f"XCHECK done {label} high={counts['high']} medium={counts['medium']} low={counts['low']} report={report}", flush=True)
    return findings


def branch_heads(root: Path) -> list[str]:
    return [l.strip() for l in git(["for-each-ref", "--format=%(objectname)", "refs/heads", "refs/remotes"], root).splitlines() if l.strip()]


def new_commits(root: Path, seen: set[str]) -> list[str]:
    heads = branch_heads(root)
    if not heads:
        return []
    shas = git(["rev-list", "--no-merges", "--reverse", "--topo-order", *heads], root).split()
    return [s for s in shas if s not in seen]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["once", "watch"])
    ap.add_argument("--rev")
    ap.add_argument("--commit", nargs="*")
    ap.add_argument("--backend")
    ap.add_argument("--interval", type=int)
    ap.add_argument("--until")
    ap.add_argument("--max-reviews", type=int)
    ap.add_argument("--check-existing", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = repo_root()
    cfg = load_config(root).get("crosscheck", {})
    backend = pick_backend(args.backend or cfg.get("backend", "auto"))

    if args.mode == "once":
        if args.commit:
            shas = args.commit
        elif args.rev:
            shas = git(["rev-list", "--no-merges", "--reverse", args.rev], root).split()
        else:
            shas = [git(["rev-parse", "HEAD"], root).strip()]
        if not shas:
            print("XCHECK error once no commits in range")
            return 1
        try:
            review(root, shas, backend, "once-" + shas[-1][:7], args.dry_run)
        except Exception as e:  # report and fail; the human decides
            print(f"XCHECK error once {e}")
            return 1
        return 0

    seen_file = state_dir(root) / "crosscheck-seen.txt"
    seen = set(seen_file.read_text().split()) if seen_file.exists() else set()
    if not seen and not args.check_existing:
        seen = set(git(["rev-list", "--all"], root).split())
        seen_file.write_text("\n".join(sorted(seen)))
        print(f"XCHECK start watch baseline={len(seen)} commits backend={backend}", flush=True)
    interval = args.interval or int(cfg.get("interval_s", 90))
    budget = args.max_reviews or int(cfg.get("max_reviews", 40))
    reviews = 0
    while True:
        if args.until and dt.datetime.now().strftime("%H:%M") >= args.until:
            print("XCHECK done watch reached --until")
            return 0
        if git(["remote"], root).strip():
            git(["fetch", "--quiet", "--all"], root)
        for sha in new_commits(root, seen):
            if reviews >= budget:
                print(f"XCHECK done watch budget of {budget} reviews used")
                return 0
            subject = git(["log", "-1", "--format=%s", sha], root).strip()
            label = f"{sha[:7]}-" + re.sub(r"[^a-zA-Z0-9]+", "-", subject)[:40].strip("-")
            try:
                review(root, [sha], backend, label, args.dry_run)
            except Exception as e:
                print(f"XCHECK error {label} {e}", flush=True)
            seen.add(sha)
            reviews += 1
            with seen_file.open("a") as fh:
                fh.write(sha + "\n")
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main())
