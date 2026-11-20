"""Set, extend, show or clear this checkout's stream ownership (.hk/state/owns).

  ./hk own SERVER            take the globs listed for SERVER in .hk/config.json "ownership"
  ./hk own SERVER --add 'web/src/api.ts'   add a path the human explicitly reassigned
  ./hk own --show | --clear
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hkcommon import load_config, read_owns, repo_root, state_dir  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("stream", nargs="?")
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--clear", action="store_true")
    args = ap.parse_args()
    root = repo_root()
    path = state_dir(root) / "owns"
    if args.clear:
        path.unlink(missing_ok=True)
        print("[hk] ownership cleared: this checkout is unrestricted")
        return 0
    if args.show or not args.stream:
        stream, globs = read_owns(root)
        print(f"[hk] stream {stream}: {', '.join(globs)}" if stream else "[hk] unrestricted (no stream set)")
        return 0
    ownership = load_config(root).get("ownership", {})
    stream, globs = read_owns(root)
    if stream != args.stream:
        if args.stream not in ownership:
            print(f"[hk] unknown stream {args.stream!r}; known: {', '.join(ownership) or 'none'}")
            return 2
        globs = list(ownership[args.stream])
    globs += [g for g in args.add if g not in globs]
    path.write_text("\n".join([f"stream: {args.stream}", *globs]) + "\n")
    print(f"[hk] this checkout is stream {args.stream}: {', '.join(globs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
