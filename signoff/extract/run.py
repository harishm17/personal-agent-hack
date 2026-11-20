"""Reads data/pool/*.json and writes data/figures/<store>.json.

    uv run python -m signoff.extract.run                      # every store, the configured reader
    uv run python -m signoff.extract.run --model claude-sonnet-5-5 --out data/figures/_runs/sonnet
    uv run python -m signoff.extract.run --pool-dir ../stream-STORE/data/pool --limit 5

The model proposes; `spans.finish` (code) finds each quote in the store's text. A product read before with
the same text and reader is not read again (the log in <out>/_runs/ remembers), so a rerun is cheap.
"""
import argparse
import concurrent.futures
import datetime
import hashlib
import json
import os
import pathlib
import sys
import time

from signoff import config
from signoff.extract import reader, spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def pool_dir():
    for folder in (os.environ.get("SIGNOFF_POOL_DIR"), ROOT / "data" / "pool"):
        if folder and any(pathlib.Path(folder).glob("*.json")):
            return pathlib.Path(folder)
    return None


def text_key(product, model):
    return hashlib.sha256(("%s\n%s\n%s" % (model, reader.SYSTEM, product.get("text") or "")).encode()).hexdigest()[:16]


def read_one(product, sheet, model, assume_unit):
    started = time.time()
    proposals, extractor, usage, asked = reader.read(product, sheet, model)
    figures = [spans.finish(p, product, extractor, assume_unit) for p in proposals]
    return {"store": product["store"], "product_id": product["product_id"], "title": product.get("title"),
            "key": text_key(product, model), "asked": asked, "extractor": extractor, "proposals": proposals,
            "figures": figures, "usage": usage, "seconds": round(time.time() - started, 2),
            "read_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}


def run(pool_files, sheet, model, out, workers=8, limit=None, force=False, assume_unit=None, quiet=False):
    out = pathlib.Path(out)
    (out / "_runs").mkdir(parents=True, exist_ok=True)
    summary = {"products": 0, "read_now": 0, "figures": 0, "span_found": 0, "span_not_found": 0, "unsure": 0,
               "errors": []}
    for path in pool_files:
        products = json.loads(pathlib.Path(path).read_text())[:limit]
        if not products:
            continue
        store = products[0]["store"]
        log_path = out / "_runs" / (store + ".json")
        log = {} if force or not log_path.exists() else {r["product_id"]: r for r in json.loads(log_path.read_text())}
        todo = [p for p in products if log.get(p["product_id"], {}).get("key") != text_key(p, model)]
        with concurrent.futures.ThreadPoolExecutor(workers) as pool:
            jobs = {pool.submit(read_one, p, sheet, model, assume_unit): p for p in todo}
            for job in concurrent.futures.as_completed(jobs):
                p = jobs[job]
                try:
                    log[p["product_id"]] = job.result()
                    summary["read_now"] += 1
                except Exception as error:  # noqa: BLE001
                    summary["errors"].append("%s %s: %s" % (store, p["product_id"], str(error)[:200]))
        rows = [log[p["product_id"]] for p in products if p["product_id"] in log]
        figures = [f for r in rows for f in r["figures"]]
        log_path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
        (out / (store + ".json")).write_text(json.dumps(figures, indent=1, ensure_ascii=False) + "\n")
        summary["products"] += len(products)
        summary["figures"] += len(figures)
        summary["span_found"] += sum(1 for f in figures if f["span_found_in_text"])
        summary["span_not_found"] += sum(1 for f in figures if not f["span_found_in_text"])
        summary["unsure"] += sum(1 for f in figures if f.get("unsure"))
        if not quiet:
            print("%s: %d products, %d figures, %d with a found span, %d unsure" % (
                store, len(products), len(figures), sum(1 for f in figures if f["span_found_in_text"]),
                sum(1 for f in figures if f.get("unsure"))))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pool-dir", default=None, help="default: $SIGNOFF_POOL_DIR, then data/pool")
    ap.add_argument("--out", default=str(ROOT / "data" / "figures"))
    ap.add_argument("--sheet", default=os.environ.get("SIGNOFF_SHEET") or "sheet1")
    ap.add_argument("--model", default=config.env("SIGNOFF_READER_MODEL") or reader.DEFAULT_MODEL)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="first N products of each store")
    ap.add_argument("--force", action="store_true", help="read every product again")
    ap.add_argument("--assume-unit", default=None, help="unit for numbers the page gives without one (off by default)")
    args = ap.parse_args(argv)
    folder = pathlib.Path(args.pool_dir) if args.pool_dir else pool_dir()
    if folder is None:
        files = [ROOT / "fixtures" / "pool.json"]
        print("no data/pool yet: reading fixtures/pool.json", file=sys.stderr)
    else:
        files = sorted(folder.glob("*.json"))
    sheet = json.loads((ROOT / "sheets" / (args.sheet + ".json")).read_text())
    summary = run(files, sheet, args.model, args.out, args.workers, args.limit, args.force, args.assume_unit)
    print(json.dumps(summary))
    return 1 if summary["errors"] and not summary["figures"] else 0


if __name__ == "__main__":
    sys.exit(main())
