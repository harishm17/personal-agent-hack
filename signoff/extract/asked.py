"""Reads what each store's own agent replied when asked about a figure (the STORE stream asks and caches the
replies in data/store_answers/asked/; the question is built by code from the product title and the figure
name, and never holds a limit).

    uv run python -m signoff.extract.asked        # reads every reply once, writes data/figures/_asked/<store>.json

The same reader and the same span check as for a product page, with the reply as the text: the model proposes
the figure and the reply's own words, code finds those words in the reply and checks the number is in them.
`answered` is true only when that holds and the reader did not mark it unsure. A reply that says the store's
information does not give the figure is `answered: false`, which is a result, not a failure.

Display only. The pick rule never sees these rows: they are attached to a candidate as `asked`.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import sys

from signoff import config
from signoff.extract import reader, spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
REPLIES = ROOT / "data" / "store_answers" / "asked"
OUT = ROOT / "data" / "figures" / "_asked"


def key_of(row, model):
    return hashlib.sha256(("%s\n%s\n%s\n%s" % (model, reader.SYSTEM, row.get("figure"), row.get("reply") or "")).encode()).hexdigest()[:16]


def read_reply(row, sheet, model):
    """One reply through the reader: the row plus quote, start, end, value, unit and `answered`."""
    out = {k: row.get(k) for k in ("store", "product_id", "figure", "question", "reply", "asked_at", "role", "line_id")}
    out.update(quote=None, start=None, end=None, value=None, low=None, high=None, kind=None, unit=None,
               answered=False, extractor=None, key=key_of(row, model),
               read_at=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
    figure, reply = row.get("figure"), row.get("reply") or ""
    units = reader.figure_units(sheet)
    if figure not in units or not reply.strip():  # a returns-and-delivery reply, or nothing came back: shown as it is
        out["answered"] = None if figure not in units else False
        return out
    page = {"store": row["store"], "product_id": row["product_id"], "text": reply}
    text, _, extractor = reader.ask(model, reader.SYSTEM, reader.prompt_for(page, [figure], sheet),
                                    purpose="read a figure from the store agent's reply")
    out["extractor"] = extractor
    proposals = [p for p in reader.parse(text) if p.get("stated") and p.get("figure") == figure]
    if not proposals:
        return out
    made = spans.finish(proposals[0], page, extractor, None, units[figure])
    out.update({k: made.get(k) for k in ("quote", "start", "end", "value", "low", "high", "kind", "unit")})
    out["span_found_in_text"] = made["span_found_in_text"]
    if made.get("unsure"):
        out["unsure_reason"] = made.get("unsure_reason")
    out["answered"] = bool(made["span_found_in_text"] and not made.get("unsure"))
    return out


def dirs(sheet_id):
    """(replies, output) of a sheet: the STORE stream's replies and where their readings are cached."""
    if sheet_id == "sheet1":
        return REPLIES, OUT
    return ROOT / "data" / sheet_id / "store_answers" / "asked", ROOT / "data" / "figures" / sheet_id / "_asked"


def run(model, replies=None, out=None, workers=8, force=False, sheet_id="sheet1"):
    sheet = json.loads((ROOT / "sheets" / (sheet_id + ".json")).read_text())
    replies, out = replies or dirs(sheet_id)[0], out or dirs(sheet_id)[1]
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary = {"replies": 0, "read_now": 0, "about_a_figure": 0, "answered": 0, "errors": []}
    for path in sorted(pathlib.Path(replies).glob("*.json")):
        rows = json.loads(path.read_text())
        held_path = out / path.name
        held = {} if force or not held_path.exists() else {(r["product_id"], r["figure"], r["question"]): r
                                                         for r in json.loads(held_path.read_text())}
        done = {}
        todo = [r for r in rows if held.get((r["product_id"], r["figure"], r["question"]), {}).get("key") != key_of(r, model)]
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            jobs = {pool.submit(read_reply, r, sheet, model): r for r in todo}
            for job in concurrent.futures.as_completed(jobs):
                r = jobs[job]
                try:
                    done[(r["product_id"], r["figure"], r["question"])] = job.result()
                except Exception as error:  # noqa: BLE001
                    summary["errors"].append("%s %s: %s" % (r["store"], r["figure"], str(error)[:160]))
        made = [done.get(k) or held.get(k) for k in ((r["product_id"], r["figure"], r["question"]) for r in rows)]
        made = [m for m in made if m]
        held_path.write_text(json.dumps(made, indent=1, ensure_ascii=False) + "\n")
        summary["replies"] += len(rows)
        summary["read_now"] += len(done)
        summary["about_a_figure"] += sum(1 for m in made if m["answered"] is not None)
        summary["answered"] += sum(1 for m in made if m["answered"])
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", default=os.environ.get("SIGNOFF_SHEET") or "sheet1")
    ap.add_argument("--replies", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--model", default=config.env("SIGNOFF_READER_MODEL") or reader.DEFAULT_MODEL)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)
    summary = run(args.model, args.replies, args.out, force=args.force, sheet_id=args.sheet)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
