"""Check the submission draft and the repo before the form is sent.

  ./hk submit [--no-net] [--file SUBMISSION.md]

SUBMISSION.md holds one heading per form field, with flags in the brackets at the end of the heading:
  ## Project name (required, max 140)
  ## Demo video URL (required, url)
  ## Live app URL (optional, url)
The text under a heading is the answer; HTML comments are ignored.
Checks: required fields filled, no <placeholder> left, length limits, URLs open without a login,
working tree clean, HEAD pushed, .env never committed, no key-shaped strings in tracked files.
Prints one PASS / WARN / FAIL line per check and exits 0 when nothing fails.
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import clock_line, git, load_config, repo_root  # noqa: E402

KEY_PATTERN = (r"(sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[A-Za-z0-9]{30,}"
               r"|xox[abp]-[A-Za-z0-9-]{20,}|tgr_[A-Za-z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----)")
PLACEHOLDER = re.compile(r"<[A-Za-z][^<>\n]*>")


def parse_fields(text: str) -> list[dict]:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    fields = []
    for block in re.split(r"^## +", text, flags=re.M)[1:]:
        heading, _, body = block.partition("\n")
        flags_match = re.search(r"\(([^()]*)\)\s*$", heading)
        flags = [f.strip().lower() for f in flags_match.group(1).split(",")] if flags_match else []
        limit = next((int(f.split()[1]) for f in flags if re.fullmatch(r"max \d+", f)), None)
        fields.append({"name": (heading[:flags_match.start()] if flags_match else heading).strip(),
                       "required": "required" in flags, "url": "url" in flags, "max": limit,
                       "body": body.strip()})
    return fields


def url_status(url: str) -> str:
    """Return '' when the URL opens without a login, else the reason."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (hk submit check)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            final = resp.geturl()
            if re.search(r"/(login|signin|accounts)\b", final) and final != url:
                return f"redirects to a login page ({final[:60]})"
            return ""
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}" + (" (private or missing)" if e.code in (401, 403, 404) else "")
    except Exception as e:  # DNS, TLS, timeout
        return f"{type(e).__name__}: {str(e)[:80]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-net", action="store_true", help="skip opening the URLs")
    ap.add_argument("--file", default="SUBMISSION.md")
    args = ap.parse_args()
    root = repo_root()
    fails = 0

    def say(level: str, what: str, detail: str = "") -> None:
        nonlocal fails
        fails += level == "FAIL"
        print(f"  {level:<4} {what}{': ' + detail if detail else ''}")

    line = clock_line(load_config(root), verbose=False)
    if line:
        print(line)
    path = root / args.file
    if not path.exists():
        print(f"[hk] {args.file} not found; copy the form's fields into it first")
        return 2

    print(f"[hk] fields in {args.file}")
    for f in parse_fields(path.read_text()):
        body, name = f["body"], f["name"]
        if not body or PLACEHOLDER.fullmatch(body):
            say("FAIL" if f["required"] else "PASS", name, "empty" + ("" if f["required"] else ", optional"))
            continue
        left = PLACEHOLDER.search(body)
        if left:
            say("FAIL", name, f"placeholder left: {left.group(0)[:40]}")
            continue
        if f["max"] is not None and len(body) > f["max"]:
            say("FAIL", name, f"{len(body)} characters, limit {f['max']} (cut {len(body) - f['max']})")
            continue
        detail = f"{len(body)}/{f['max']} characters" if f["max"] is not None else ""
        if f["url"]:
            url = body.split()[0]
            if not re.match(r"https?://", url):
                say("FAIL", name, f"not a URL: {url[:50]}")
                continue
            if not args.no_net:
                why = url_status(url)
                if why:
                    say("FAIL" if f["required"] else "WARN", name, f"{url} {why}")
                    continue
                detail = "opens without a login"
        say("PASS", name, detail)

    print("[hk] repo")
    dirty = [l for l in git(["status", "--porcelain"], root).splitlines() if l.strip()]
    say("WARN" if dirty else "PASS", "working tree", f"{len(dirty)} uncommitted change(s)" if dirty else "clean")
    if not git(["remote"], root).strip():
        say("FAIL", "remote", "no git remote; create the repo and push")
    elif not git(["branch", "-r", "--contains", "HEAD"], root).strip():
        say("FAIL", "pushed", "HEAD is not on any remote branch; push it")
    else:
        say("PASS", "pushed", "HEAD is on the remote")
    if git(["log", "--all", "--oneline", "--", ".env"], root).strip():
        say("FAIL", "secrets", ".env is in the git history; rotate those keys and remove it")
    hits = [l for l in git(["grep", "-nIE", "-e", KEY_PATTERN, "--", ".", ":!scripts/hk/submit_check.py"], root).splitlines() if l]
    if hits:
        where = ", ".join(":".join(h.split(":")[:2]) for h in hits[:5])
        say("FAIL", "secrets", f"key-shaped string in {where}")
    elif not git(["log", "--all", "--oneline", "--", ".env"], root).strip():
        say("PASS", "secrets", "no .env in history, no key-shaped strings in tracked files")

    print(f"[hk] submit check: {'ready' if not fails else str(fails) + ' thing(s) to fix'}"
          " · open the video and repo links in a private window before you send the form")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
