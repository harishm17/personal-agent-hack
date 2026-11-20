"""What each reading call was given, and what it was not: one committed row per model call behind the readings.

    uv run python -m signoff.extract.ledger --sheet sheet4     # rebuilds <figures>/_runs/read_ledger.jsonl

The outbound ledger of the running app (signoff.obs.egress) is a local file that is not committed, so the calls
that produced the committed readings would be missing from it on another checkout. This file travels with the
readings. A row is written when a page is read; for readings already cached, a row is rebuilt only when the
cached reading's key matches the prompt this code builds today for the same page text and the same sheet words,
so the bytes and the hash are those of the prompt that was sent. A row says:
- `parts`: what the prompt was built from, with sizes: the reading instructions, the figure names with their
  units and meanings from the sheet, and the store's page text for that option;
- `withheld`: what was not in it, by construction of `reader.prompt_for`: limits and their values, the home's
  measurements, prices, other pages and other stores, the order document, the people on the sheet;
- `tools`: 0. No reading call is given a tool.
"""
import argparse
import hashlib
import json
import os
import pathlib
import sys

from signoff.engine import paths, rules
from signoff.extract import gliner, reader, run

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
WITHHELD = ["limits and their values", "the home's measurements", "prices", "other pages and other stores",
            "the order document", "the people on the sheet"]
# Measured once by capturing a call on this machine: besides our two strings the command-line tool sends its own
# note. None of it comes from the sheet; it is said here so that a row does not claim more than is true.
CLI_ADDS = ("the command-line tool adds a note with the logged-in account's address and a description of the local "
            "environment, and makes a second call that titles the session from the same text; `bytes` counts our prompt only")
TRANSPORT = {"anthropic": "claude -p, no tools, outside the repository", "sie": "Superlinked SIE, chat endpoint, no tools",
             "sie-extract": "Superlinked SIE, extract endpoint (labels and text only)"}


def row_for(page, sheet, model, extractor, read_at, rebuilt=False, system=None):
    """One ledger row for one reading call on one page. `system` is the instructions as they were sent."""
    system = system or reader.SYSTEM
    asked = reader.wanted_figures(page, sheet)
    text = page.get("text") or ""
    if model == gliner.EXTRACTOR:
        labels = [gliner.LABELS.get(n, n.replace("_", " ")) for n in asked]
        payload = json.dumps({"text": text, "labels": labels}, ensure_ascii=False, sort_keys=True)
        parts = [{"what": "labels: the figure names as words", "bytes": len(json.dumps(labels).encode()), "figures": asked},
                 {"what": "the store's page text for this option", "bytes": len(text.encode())}]
        transport = TRANSPORT["sie-extract"]
    else:
        user = reader.prompt_for(page, asked, sheet)
        payload = json.dumps({"system": system, "user": user}, ensure_ascii=False, sort_keys=True)
        parts = [{"what": "reading instructions (the same for every page)", "bytes": len(system.encode())},
                 {"what": "figure names with their units and meanings, from the sheet", "figures": asked,
                  "bytes": len(user.encode()) - len(text.encode())},
                 {"what": "the store's page text for this option", "bytes": len(text.encode())}]
        transport = TRANSPORT["anthropic" if extractor.startswith("anthropic") else "sie"]
    raw = payload.encode()
    return {"sheet": sheet["id"], "at": read_at, "recipient": extractor, "kind": "model provider",
            "purpose": "read figures from one store page", "page": {"store": page["store"], "product_id": page["product_id"],
                                                                    "variant_id": page.get("variant_id"), "title": page.get("title"),
                                                                    "option": page.get("variant_title")},
            "bytes": len(raw), "payload_sha256": hashlib.sha256(raw).hexdigest(), "parts": parts, "withheld": WITHHELD,
            "fact_classes": ["product", "store_text"], "tools": 0, "transport": transport, "rebuilt_from_cache": rebuilt,
            **({"added_by_the_command_line": CLI_ADDS} if transport == TRANSPORT["anthropic"] else {})}


def rebuild(sheet_id):
    """Rows for every cached reading of a sheet's data folder whose prompt can be rebuilt exactly (key match)."""
    data_id = paths.data_sheet(sheet_id)
    sheet = json.loads((ROOT / "sheets" / (data_id + ".json")).read_text())
    rules.declare_units(sheet)
    where = paths.of(data_id)
    pages = {(p["product_id"], p.get("variant_id")): p for p in run.rows_of(run.pool_files(sheet_id=data_id))}
    rows, skipped = [], 0
    for folder in sorted(where["runs"].iterdir()) if where["runs"].is_dir() else []:
        for log in sorted(folder.glob("*.log")):
            for entry in json.loads(log.read_text()):
                page = pages.get((entry["product_id"], entry.get("variant_id")))
                model = gliner.EXTRACTOR if entry.get("extractor") == gliner.EXTRACTOR else \
                    entry.get("extractor", "").replace("anthropic:", "")
                sent = None if page is None or not entry.get("asked") else next(
                    (system for system in (reader.SYSTEM, reader.SYSTEM_WITH_THE_OLD_EXAMPLE)
                     if entry.get("key") == run.text_key(page, model, sheet, system)), None)
                if sent is None:
                    skipped += 1  # no figures were asked of this page, or its prompt cannot be rebuilt exactly
                    continue
                rows.append(row_for(page, sheet, model, entry["extractor"], entry.get("read_at"), rebuilt=True, system=sent))
    rows.sort(key=lambda r: (r["at"] or "", r["recipient"], r["page"]["product_id"], str(r["page"]["variant_id"])))
    for n, row in enumerate(rows, 1):
        row["n"] = n
    out = where["runs"] / "read_ledger.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    return out, len(rows), skipped


def rows(sheet_id):
    """The committed rows for the sheet's data folder, with a summary for the trail."""
    path = paths.of(paths.data_sheet(sheet_id))["runs"] / "read_ledger.jsonl"
    found = [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []
    by = {}
    for r in found:
        by.setdefault(r["recipient"], {"calls": 0, "bytes": 0})
        by[r["recipient"]]["calls"] += 1
        by[r["recipient"]]["bytes"] += r["bytes"]
    return {"sheet": sheet_id, "data_from": paths.data_sheet(sheet_id), "file": str(path.relative_to(ROOT)) if path.exists() else None,
            "calls": len(found), "by_recipient": by, "withheld_in_every_call": WITHHELD, "tools_in_any_call": 0, "rows": found}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", default=os.environ.get("SIGNOFF_SHEET") or "sheet1")
    args = ap.parse_args(argv)
    out, n, skipped = rebuild(args.sheet)
    print("%s: %d rows; %d cached readings left out (no figures asked, or the prompt cannot be rebuilt exactly)" % (
        out.relative_to(ROOT), n, skipped))
    return 0


if __name__ == "__main__":
    sys.exit(main())
