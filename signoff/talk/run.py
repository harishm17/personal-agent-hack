"""Command line for the TALK stream.

  uv run python -m signoff.talk.run --sheet sheet4 --state http://localhost:8800/api/state   the agent's own questions
  uv run python -m signoff.talk.run --sheet sheet4 --store carex.com --text "..." [--product ID]   one purpose
  add --dry to see the draft and the guard's decision without calling the store (nothing is saved)
"""
import argparse
import json
import os
import urllib.request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--state", help="URL of /api/state (GET) to plan from: one conversation per picked product")
    ap.add_argument("--store")
    ap.add_argument("--product")
    ap.add_argument("--text")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    os.environ["SIGNOFF_SHEET"] = a.sheet
    from signoff.store import sheetctx
    from signoff.talk import guard, talk, writer
    sheet = sheetctx.sheet(a.sheet)
    if a.state:
        with urllib.request.urlopen(a.state, timeout=30) as f:
            state = json.loads(f.read())
        if state["sheet"]["id"] != a.sheet:
            raise SystemExit("the state at %s is for %s, not %s" % (a.state, state["sheet"]["id"], a.sheet))
        targets = talk.plan(state, sheet)
    else:
        targets = [{"store": a.store, "product_id": a.product, "purpose": a.text, "origin": "shopper"}]
    for t in targets:
        if a.dry:
            prod = talk.product(t["store"], t["product_id"], a.sheet)
            d = writer.draft(t["purpose"], {"product": prod and prod["title"], "needed by": guard.need_by_text(sheet)})
            turn = talk._decide(d["message"], sheet, prod, guard.sie_finder, writer.rewrite)
            print(json.dumps({"store": t["store"], "questions": d["questions"], **turn}, indent=1, ensure_ascii=False))
            continue
        th = talk.ask(t["store"], t["purpose"], t["product_id"], sheet, origin=t.get("origin", "agent"))
        print(json.dumps(th, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
