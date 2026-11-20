"""Reads a sheet's pool and writes its figures.

    uv run python -m signoff.extract.run                    # the active sheet ($SIGNOFF_SHEET, else sheet1)
    uv run python -m signoff.extract.run --sheet sheet2
    uv run python -m signoff.extract.run --limit 5 --out /tmp/try

Every candidate page is read: one per product, or one per option on sale when the store sells several (the
option's name is the last line of the text). Each reader's own records go to <figures>/_runs/<reader>/<store>.json
with a log of every reply beside it. The models propose statements; `spans.finish` (code) finds each quote in
the store's text; `combine` writes the records the engine uses (the reference reader's). A page already read
with the same text, the same reader and the same instructions is not read again: read once, cached.

Where a sheet's files are: `signoff.engine.paths`. There is no fallback to sample data: without a pool this
stops and says so.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys
import time

from signoff import config
from signoff.engine import obs, options, paths, rules
from signoff.extract import combine, gliner, reader, spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OTHER_READERS = ["sie:Qwen/Qwen3.8-27B-FP8"]  # measured against the reference, on the same pages


def readers():
    """The reference reader first (it decides), then the readers compared with it."""
    first = config.env("SIGNOFF_READER_MODEL") or reader.DEFAULT_MODEL
    others = (config.env("SIGNOFF_OTHER_READERS") or ",".join(OTHER_READERS)).split(",")
    return [first] + [m.strip() for m in others if m.strip() and m.strip() not in ("none", first)]


def slug(name):
    return re.sub(r"[^A-Za-z0-9.]+", "-", name).strip("-")


def sheet_dirs(sheet_id):
    """(pool folder, figures folder) of a sheet."""
    where = paths.of(sheet_id)
    return where["pool"], where["figures"]


def pool_files(folder=None, sheet_id="sheet1"):
    folder = pathlib.Path(folder) if folder else paths.of(sheet_id)["pool"]
    return sorted(folder.glob("*.json")) if folder.is_dir() else []


def rows_of(files):
    """Every candidate page of a pool: one row per product, or one per option on sale."""
    return options.expand([row for path in files for row in json.loads(pathlib.Path(path).read_text())])


def text_key(product, model, sheet, system=None):
    """Same text, same reader, same instructions (the prompt and the sheet's words for the figures asked)."""
    asked = reader.wanted_figures(product, sheet)
    if model == gliner.EXTRACTOR:
        salt = gliner.MODEL + "|" + ",".join(asked)
    else:
        given, units = sheet.get("figures") or {}, reader.figure_units(sheet)
        salt = (system or reader.SYSTEM) + "".join("%s(%s):%s;" % (n, units.get(n), given.get(n)) for n in asked)
    return hashlib.sha256(("%s\n%s\n%s" % (model, salt, product.get("text") or "")).encode()).hexdigest()[:16]


def read_one(product, sheet, model, assume_unit=None):
    started = time.time()
    asked, units = reader.wanted_figures(product, sheet), reader.figure_units(sheet)
    if model == gliner.EXTRACTOR:
        proposals, extractor, usage = gliner.read(product, asked, units)
    else:
        proposals, extractor, usage, asked = reader.read(product, sheet, model)
    figures = [spans.finish(p, product, extractor, assume_unit, units.get(p.get("figure"))) for p in proposals]
    for f in figures:
        f["variant_id"] = product.get("variant_id")
    obs.tool_call("figure_read", {"store": product["store"], "product_id": product["product_id"],
                                  "variant_id": product.get("variant_id"), "reader": extractor, "asked": asked},
                  {"figures": [{"figure": f["figure"], "kind": f["kind"], "value": f["value"], "low": f["low"],
                                "high": f["high"], "span_found_in_text": f["span_found_in_text"]} for f in figures]},
                  True, int((time.time() - started) * 1000))
    return {"store": product["store"], "product_id": product["product_id"], "variant_id": product.get("variant_id"),
            "title": product.get("title"), "variant_title": product.get("variant_title"),
            "key": text_key(product, model, sheet), "asked": asked, "extractor": extractor, "proposals": proposals,
            "figures": figures, "usage": usage, "seconds": round(time.time() - started, 2),
            "read_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}


def run_reader(products, sheet, model, out, workers=8, force=False, assume_unit=None, suffix=""):
    """One reader over one store's pages. Returns (figure rows, errors, pages read now)."""
    folder = pathlib.Path(out) / "_runs" / (slug(model) + suffix)
    folder.mkdir(parents=True, exist_ok=True)
    store = products[0]["store"]
    log_path = folder / (store + ".log")
    row_key = lambda r: (r["product_id"], r.get("variant_id"))  # noqa: E731
    log = {} if force or not log_path.exists() else {row_key(r): r for r in json.loads(log_path.read_text())}
    def cached(p):
        """A reading stands when it was made with today's instructions, or with the instructions that differ
        only in the example at their end (see `reader.SYSTEM_WITH_THE_OLD_EXAMPLE`)."""
        key = log.get(row_key(p), {}).get("key")
        return key is not None and key in (text_key(p, model, sheet), text_key(p, model, sheet, reader.SYSTEM_WITH_THE_OLD_EXAMPLE))

    todo = [p for p in products if not cached(p)]
    errors = []
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        jobs = {pool.submit(read_one, p, sheet, model, assume_unit): p for p in todo}
        for job in concurrent.futures.as_completed(jobs):
            p = jobs[job]
            try:
                log[row_key(p)] = job.result()
            except Exception as error:  # noqa: BLE001
                log.pop(row_key(p), None)  # a page that could not be read has no reading; nothing stale stands in
                errors.append("%s %s %s: %s" % (model, store, p["product_id"], str(error)[:200]))
    rows = [log[row_key(p)] for p in products if row_key(p) in log]
    figures = [f for r in rows for f in r["figures"]]
    log_path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    (folder / (store + ".json")).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
    return figures, errors, len(todo) - len(errors)


def run(files, sheet, deciding, out, evidence=(), policy="first", workers=8, limit=None, force=False,
        assume_unit=None, quiet=False):
    out = pathlib.Path(out)
    summary = {"products": 0, "pages": 0, "read_now": 0, "statements": 0, "span_not_found": 0,
               "readers": list(deciding), "evidence": list(evidence), "errors": []}
    for path in files:
        listed = json.loads(pathlib.Path(path).read_text())[:limit]
        products = options.expand(listed)
        if not products:
            continue
        store, per_reader = products[0]["store"], {}
        with concurrent.futures.ThreadPoolExecutor(len(deciding) + len(evidence)) as pool:
            jobs = {m: pool.submit(run_reader, products, sheet, m, out, workers, force, assume_unit)
                    for m in list(deciding) + list(evidence)}
            for model, job in jobs.items():
                rows, errors, now = job.result()
                per_reader[model] = rows
                summary["errors"] += errors
                summary["read_now"] += now
        named = lambda m: (per_reader[m][0]["extractor"] if per_reader[m] else m, per_reader[m])  # noqa: E731
        figures = combine.combine([named(m) for m in deciding], [named(m) for m in evidence], policy)
        out.mkdir(parents=True, exist_ok=True)
        (out / (store + ".json")).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
        summary["products"] += len(listed)
        summary["pages"] += len(products)
        summary["statements"] += len(figures)
        summary["span_not_found"] += sum(1 for f in figures if not f["span_found_in_text"])
        if not quiet:
            print("%s: %d products, %d pages (options), %d statements, %d quotes not found" % (
                store, len(listed), len(products), len(figures), sum(1 for f in figures if not f["span_found_in_text"])))
    return summary


def refresh(workers=8):
    """For the app, after the pool was refetched: read what changed, combine, compare, reload the engine."""
    from signoff.engine import state
    sheet_id = state.get_state()["sheet"]["id"]
    sheet = json.loads((ROOT / "sheets" / (sheet_id + ".json")).read_text())
    rules.declare_units(sheet)
    files, out = pool_files(sheet_id=sheet_id), sheet_dirs(sheet_id)[1]
    if not files:
        return {"products": 0, "errors": ["no pool for %s" % sheet_id]}
    evidence = [gliner.EXTRACTOR] if config.have("SIE_API_KEY") else []
    summary = run(files, sheet, readers(), out, evidence, workers=workers, quiet=True)
    from signoff.extract import score
    score.write(out)
    state.reload_data()
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool-dir", default=None, help="default: the sheet's pool folder")
    ap.add_argument("--out", default=None, help="default: the sheet's figures folder")
    ap.add_argument("--sheet", default=os.environ.get("SIGNOFF_SHEET") or "sheet1")
    ap.add_argument("--sheet-file", default=None, help="a sheet file outside sheets/ (a trial wording)")
    ap.add_argument("--reader", action="append", help="a reader (repeatable, the first decides); default: the configured ones")
    ap.add_argument("--no-evidence", action="store_true", help="skip the SIE extract pass")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="first N products of each store")
    ap.add_argument("--force", action="store_true", help="read every page again")
    ap.add_argument("--second-pass", action="store_true",
                    help="read every page once more with the first reader, into _runs/<reader>-pass2, to measure how "
                         "far the reference agrees with itself; the engine's figures are not touched")
    args = ap.parse_args(argv)
    default_out = str(sheet_dirs(args.sheet)[1])
    args.out = args.out or default_out
    files = pool_files(args.pool_dir, args.sheet)
    if not files:
        print("no pool for %s under %s: nothing was read" % (args.sheet, args.pool_dir or sheet_dirs(args.sheet)[0]), file=sys.stderr)
        return 2
    sheet = json.loads(pathlib.Path(args.sheet_file or ROOT / "sheets" / (args.sheet + ".json")).read_text())
    rules.declare_units(sheet)
    try:
        reader.meanings(sorted(reader.figure_units(sheet)), sheet)
    except reader.NoMeaning as error:
        print("%s: nothing was read" % error, file=sys.stderr)
        return 2
    deciding = args.reader or readers()
    if args.second_pass:
        errors = []
        for path in files:
            products = options.expand(json.loads(pathlib.Path(path).read_text())[:args.limit])
            rows, failed, _ = run_reader(products, sheet, deciding[0], args.out, args.workers, args.force, None, "-pass2")
            errors += failed
            print("%s: second pass, %d statements" % (products[0]["store"], len(rows)))
        from signoff.extract import score
        print(json.dumps({"second_pass": deciding[0], "errors": errors, "comparison": str(score.write(args.out))}))
        return 0
    evidence = [] if args.no_evidence or not config.have("SIE_API_KEY") or gliner.EXTRACTOR in deciding else [gliner.EXTRACTOR]
    if evidence:
        gliner.warm()
    summary = run(files, sheet, deciding, args.out, evidence, "first", args.workers, args.limit, args.force)
    if args.out == default_out and not args.limit and not args.sheet_file:
        from signoff.extract import ledger, score
        summary["comparison"] = str(score.write(args.out))
        summary["read_ledger"] = "%d rows" % ledger.rebuild(args.sheet)[1]  # what each call was given, committed with the readings
    print(json.dumps(summary))
    return 1 if summary["errors"] and not summary["statements"] else 0


if __name__ == "__main__":
    sys.exit(main())
