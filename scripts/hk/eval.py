"""Run the eval set and write measured numbers for the README and the pitch.

  ./hk eval [--cases evals/cases.jsonl] [--cmd '<shell>'] [--only id1,id2] [--workers 4]

Each line of the cases file is JSON:
  {"id": "tub-gfci", "input": <anything>, "expect": <anything>, "match": "contains"}
match: exact | contains | regex | jsonsubset (expected object is a subset of the parsed output)
The command (config "eval.cmd" or --cmd) receives the case "input" on stdin (strings as-is, other
values as JSON) and prints its answer on stdout. Writes evals/report.md and evals/report.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import load_config, repo_root  # noqa: E402


def subset(expected, actual) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(any(subset(e, a) for a in actual) for e in expected)
    return expected == actual


def judge(case: dict, output: str) -> bool:
    expect, how = case.get("expect"), case.get("match", "contains")
    text = output.strip()
    if how == "exact":
        return text == (expect if isinstance(expect, str) else json.dumps(expect))
    if how == "contains":
        needles = expect if isinstance(expect, list) else [expect]
        return all(str(n).lower() in text.lower() for n in needles)
    if how == "regex":
        return re.search(str(expect), text, re.S) is not None
    if how == "jsonsubset":
        try:
            return subset(expect, json.loads(text))
        except json.JSONDecodeError:
            return False
    raise ValueError(f"unknown match {how!r} in case {case.get('id')}")


def run_case(case: dict, cmd: str, root: Path, timeout: int) -> dict:
    payload = case.get("input")
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    started = time.time()
    try:
        p = subprocess.run(["bash", "-lc", cmd], input=stdin, capture_output=True, text=True,
                           timeout=timeout, cwd=root, env=dict(os.environ, HK_HOOKS="off"))
        output, error = p.stdout, (p.stderr[-300:] if p.returncode else "")
    except subprocess.TimeoutExpired:
        output, error = "", f"timeout after {timeout}s"
    secs = time.time() - started
    try:
        ok = (not error) and judge(case, output)
    except ValueError as e:
        ok, error = False, str(e)
    return {"id": case.get("id"), "pass": ok, "seconds": round(secs, 2), "error": error,
            "output": output.strip()[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases")
    ap.add_argument("--cmd")
    ap.add_argument("--only")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    root = repo_root()
    cfg = load_config(root).get("eval", {})
    cmd = args.cmd or cfg.get("cmd")
    if not cmd:
        print("[hk] set \"eval\": {\"cmd\": ...} in .hk/config.json or pass --cmd")
        return 2
    cases_path = root / (args.cases or cfg.get("cases", "evals/cases.jsonl"))
    cases = [json.loads(l) for l in cases_path.read_text().splitlines() if l.strip() and not l.startswith("//")]
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.get("id") in wanted]
    timeout = int(cfg.get("timeout_s", 120))
    with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda c: run_case(c, cmd, root, timeout), cases))
    passed = sum(r["pass"] for r in results)
    secs = [r["seconds"] for r in results] or [0]
    p95 = sorted(secs)[max(0, int(round(0.95 * len(secs))) - 1)]
    summary = {"cases": len(results), "passed": passed,
               "pass_rate": round(passed / len(results), 3) if results else 0,
               "median_s": round(statistics.median(secs), 2), "p95_s": p95,
               "at": time.strftime("%Y-%m-%d %H:%M"), "cmd": cmd}
    out_dir = cases_path.parent
    (out_dir / "report.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    rows = [f"| {r['id']} | {'PASS' if r['pass'] else 'FAIL'} | {r['seconds']} | {r['error'] or r['output'][:80]} |" for r in results]
    (out_dir / "report.md").write_text("\n".join([
        f"# Eval report ({summary['at']})", "",
        f"**{passed}/{len(results)} passed ({summary['pass_rate']:.0%})**, median {summary['median_s']} s, p95 {p95} s.",
        f"Command: `{cmd}`", "", "| case | result | seconds | detail |", "|---|---|---|---|", *rows, ""]))
    print(f"[hk] eval {passed}/{len(results)} passed ({summary['pass_rate']:.0%}), median {summary['median_s']}s, "
          f"p95 {p95}s -> {out_dir / 'report.md'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
