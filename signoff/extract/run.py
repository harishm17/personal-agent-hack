"""Reads data/pool/*.json and writes data/figures/<store>.json.

    uv run python -m signoff.extract.run                 # the configured readers, then combine
    uv run python -m signoff.extract.run --reader sie:Qwen/Qwen3.8-27B-FP8 --policy first
    uv run python -m signoff.extract.run --limit 5 --out /tmp/try

Each reader's own records go to <out>/_runs/<reader>/<store>.json (with a log of every reply beside it).
The models propose; `spans.finish` (code) finds each quote in the store's text; `combine` (code) writes the
one record per figure the engine uses. A product already read with the same text and reader is not read
again, so a rerun is cheap and works offline.
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
from signoff.extract import combine, gliner, reader, spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OTHER_READERS = ["sie:Qwen/Qwen3.8-27B-FP8"]  # measured as agreement with the reference, on the same products


def readers():
    """The reference reader first (it decides), then the readers compared with it."""
    first = config.env("SIGNOFF_READER_MODEL") or reader.DEFAULT_MODEL
    others = (config.env("SIGNOFF_OTHER_READERS") or ",".join(OTHER_READERS)).split(",")
    return [first] + [m.strip() for m in others if m.strip() and m.strip() not in ("none", first)]


def slug(name):
    return re.sub(r"[^A-Za-z0-9.]+", "-", name).strip("-")


def pool_files(folder=None):
    for candidate in (folder, os.environ.get("SIGNOFF_POOL_DIR"), ROOT / "data" / "pool"):
        if candidate and any(pathlib.Path(candidate).glob("*.json")):
            return sorted(pathlib.Path(candidate).glob("*.json"))
    return []


def text_key(product, model):
    salt = gliner.MODEL if model == gliner.EXTRACTOR else reader.SYSTEM
    return hashlib.sha256(("%s\n%s\n%s" % (model, salt, product.get("text") or "")).encode()).hexdigest()[:16]


def read_one(product, sheet, model, assume_unit):
    started = time.time()
    asked = reader.wanted_figures(product, sheet)
    if model == gliner.EXTRACTOR:
        proposals, extractor, usage = gliner.read(product, asked)
    else:
        proposals, extractor, usage, asked = reader.read(product, sheet, model)
    figures = [spans.finish(p, product, extractor, assume_unit) for p in proposals]
    return {"store": product["store"], "product_id": product["product_id"], "title": product.get("title"),
            "key": text_key(product, model), "asked": asked, "extractor": extractor, "proposals": proposals,
            "figures": figures, "usage": usage, "seconds": round(time.time() - started, 2),
            "read_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}


def run_reader(products, sheet, model, out, workers=8, force=False, assume_unit=None):
    """One reader over one store's products. Returns (figure rows, errors, products read now)."""
    folder = pathlib.Path(out) / "_runs" / slug(model)
    folder.mkdir(parents=True, exist_ok=True)
    store = products[0]["store"]
    log_path = folder / (store + ".log")
    log = {} if force or not log_path.exists() else {r["product_id"]: r for r in json.loads(log_path.read_text())}
    todo = [p for p in products if log.get(p["product_id"], {}).get("key") != text_key(p, model)]
    errors = []
    with concurrent.futures.ThreadPoolExecutor(workers) as pool:
        jobs = {pool.submit(read_one, p, sheet, model, assume_unit): p for p in todo}
        for job in concurrent.futures.as_completed(jobs):
            p = jobs[job]
            try:
                log[p["product_id"]] = job.result()
            except Exception as error:  # noqa: BLE001
                errors.append("%s %s %s: %s" % (model, store, p["product_id"], str(error)[:200]))
    rows = [log[p["product_id"]] for p in products if p["product_id"] in log]
    figures = [f for r in rows for f in r["figures"]]
    log_path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
    (folder / (store + ".json")).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
    return figures, errors, len(todo) - len(errors)


def run(files, sheet, deciding, out, evidence=(), policy="first", workers=8, limit=None, force=False,
        assume_unit=None, quiet=False):
    out = pathlib.Path(out)
    summary = {"products": 0, "read_now": 0, "figures": 0, "counted": 0, "unsure": 0, "span_not_found": 0,
               "readers": list(deciding), "evidence": list(evidence), "policy": policy, "errors": []}
    for path in files:
        products = json.loads(pathlib.Path(path).read_text())[:limit]
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
        (out / (store + ".json")).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
        summary["products"] += len(products)
        summary["figures"] += len(figures)
        summary["counted"] += sum(1 for f in figures if combine.counted(f))
        summary["unsure"] += sum(1 for f in figures if f.get("unsure"))
        summary["span_not_found"] += sum(1 for f in figures if not f["span_found_in_text"])
        if not quiet:
            print("%s: %d products, %d figures, %d count, %d unsure" % (
                store, len(products), len(figures), sum(1 for f in figures if combine.counted(f)),
                sum(1 for f in figures if f.get("unsure"))))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool-dir", default=None, help="default: $SIGNOFF_POOL_DIR, then data/pool")
    ap.add_argument("--out", default=str(ROOT / "data" / "figures"))
    ap.add_argument("--sheet", default=os.environ.get("SIGNOFF_SHEET") or "sheet1")
    ap.add_argument("--reader", action="append", help="a reader (repeatable, the first decides); default: the configured ones")
    ap.add_argument("--policy", choices=("agree", "first"), default=config.env("SIGNOFF_READER_POLICY") or "first")
    ap.add_argument("--no-evidence", action="store_true", help="skip the SIE extract pass")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="first N products of each store")
    ap.add_argument("--force", action="store_true", help="read every product again")
    ap.add_argument("--assume-unit", default=None, help="unit for numbers the page gives without one (off by default)")
    args = ap.parse_args(argv)
    files = pool_files(args.pool_dir)
    if not files:
        files = [ROOT / "fixtures" / "pool.json"]
        print("no data/pool yet: reading fixtures/pool.json", file=sys.stderr)
    sheet = json.loads((ROOT / "sheets" / (args.sheet + ".json")).read_text())
    deciding = args.reader or readers()
    evidence = [] if args.no_evidence or not config.have("SIE_API_KEY") or gliner.EXTRACTOR in deciding else [gliner.EXTRACTOR]
    if evidence:
        gliner.warm()
    summary = run(files, sheet, deciding, args.out, evidence, args.policy, args.workers, args.limit, args.force,
                  args.assume_unit)
    if args.out == str(ROOT / "data" / "figures") and not args.limit:
        from signoff.extract import score
        summary["comparison"] = str(score.write(args.out))
    print(json.dumps(summary))
    return 1 if summary["errors"] and not summary["figures"] else 0


if __name__ == "__main__":
    sys.exit(main())
