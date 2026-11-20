"""How far each reader agrees with the reference reader on the same products. Agreement, not accuracy:
nobody hand-read these pages; the reference is `claude-sonnet-5-5` (CONTRACT.md, amendment 11:25).

    uv run python -m signoff.extract.score            # prints the table, writes data/figures/_runs/comparison.json
    uv run python -m signoff.extract.score --detail   # also every figure where a reader differs

For each reader: the share of its figures whose quote was found in the store's text, how many of the
reference's counted figures it gives with the same kind and numbers, how many it reads differently, misses
or adds, and its time and cost per product from the run logs. A figure "counts" for a reader when its span
was found and the reader did not mark it unsure, which is what the engine would use.
"""
import argparse
import datetime
import json
import pathlib
import statistics
import sys

from signoff.extract import combine

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
FIGURES = ROOT / "data" / "figures"


def load_run(folder):
    """(extractor name, {(store, product, figure): row}, log rows) for one reader's folder."""
    rows, log = [], []
    for path in sorted(folder.glob("*.json")):
        rows.extend(json.loads(path.read_text()))
    for path in sorted(folder.glob("*.log")):
        log.extend(json.loads(path.read_text()))
    index = {}
    for r in rows:
        index.setdefault((r["store"], r["product_id"], r["figure"]), r)
    name = log[0]["extractor"] if log else (rows[0]["extractor"] if rows else folder.name)
    return name, index, log


def cost(log):
    usd = [r["usage"].get("cost_usd") for r in log if isinstance(r.get("usage"), dict) and r["usage"].get("cost_usd")]
    credits = [float(r["usage"].get("credits_charged_decimal") or r["usage"].get("credits_charged"))
               for r in log if isinstance(r.get("usage"), dict) and r["usage"].get("credits_charged") is not None]
    out = {}
    if usd:
        out["usd_total"] = round(sum(usd), 4)
        out["usd_per_product"] = round(sum(usd) / len(log), 5)
    if credits:
        out["sie_credits_total"] = round(sum(credits), 2)
        out["sie_credits_per_product"] = round(sum(credits) / len(log), 3)
    return out or None


def measure(name, index, log, reference):
    counted = {k: r for k, r in index.items() if combine.counted(r)}
    ref = {k: r for k, r in reference.items() if combine.counted(r)}
    same = [k for k in ref if k in counted and combine.same(ref[k], counted[k])]
    different = [k for k in ref if k in counted and not combine.same(ref[k], counted[k])]
    missing = [k for k in ref if k not in counted]
    extra = [k for k in counted if k not in ref]
    products = {(r["store"], r["product_id"]) for r in log}
    clean = products - {k[:2] for k in different + missing + extra}
    seconds = [r["seconds"] for r in log if r.get("seconds") is not None]
    return {
        "extractor": name, "products_read": len(products),
        "figures_reported": len(index),
        "span_found": sum(1 for r in index.values() if r.get("span_found_in_text")),
        "span_found_share": round(sum(1 for r in index.values() if r.get("span_found_in_text")) / len(index), 3) if index else None,
        "marked_unsure": sum(1 for r in index.values() if r.get("unsure")),
        "figures_counted": len(counted),
        "reference_figures": len(ref), "same_as_reference": len(same),
        "agreement": round(len(same) / len(ref), 3) if ref else None,
        "different_number": len(different), "missing": len(missing), "extra": len(extra),
        "products_fully_agreeing": len(clean),
        "seconds_per_product_median": round(statistics.median(seconds), 2) if seconds else None,
        "seconds_per_product_mean": round(statistics.mean(seconds), 2) if seconds else None,
        "cost": cost(log),
        "differences": [{"store": k[0], "product_id": k[1], "figure": k[2], "kind": kind,
                         "reference": combine.shown(ref[k]) if k in ref else None,
                         "reference_quote": ref[k]["quote"] if k in ref else None,
                         "reader": combine.shown(index[k]) if k in index and index[k].get("kind") and
                         (index[k].get("value") is not None or index[k].get("low") is not None) else None,
                         "reader_quote": index[k]["quote"] if k in index else None,
                         "reader_unsure": index[k].get("unsure_reason") if k in index else None,
                         "reference_unsure": reference[k].get("unsure_reason") if k in reference else None}
                        for kind, keys in (("different_number", different), ("missing", missing), ("extra", extra))
                        for k in sorted(keys)],
    }


def compare(figures=FIGURES, reference=None):
    runs = [load_run(f) for f in sorted((pathlib.Path(figures) / "_runs").iterdir()) if f.is_dir()]
    if not runs:
        raise SystemExit("no reader runs under %s/_runs" % figures)
    ref = next((r for r in runs if reference and reference in r[0]), None) or \
        next((r for r in runs if "claude-sonnet" in r[0]), runs[0])
    readers = [measure(name, index, log, ref[1]) for name, index, log in runs]
    readers.sort(key=lambda r: (r["extractor"] != ref[0], -(r["agreement"] or 0)))
    return {"made_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "reference": ref[0], "measure": "agreement with the reference reader on the same products",
            "note": "Agreement, not accuracy: no person read these pages. A figure counts when its quote is "
                    "found in the store's text and the reader did not mark it unsure.",
            "products": len({(r["store"], r["product_id"]) for r in ref[2]}), "readers": readers}


def write(figures=FIGURES, reference=None):
    path = pathlib.Path(figures) / "_runs" / "comparison.json"
    path.write_text(json.dumps(compare(figures, reference), indent=1, ensure_ascii=False) + "\n")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--figures", default=str(FIGURES))
    ap.add_argument("--reference", default=None, help="part of the reference extractor's name")
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args(argv)
    result = json.loads(write(args.figures, args.reference).read_text())
    print("reference: %s · %d products · %s" % (result["reference"], result["products"], result["measure"]))
    for r in result["readers"]:
        print("%-34s agrees on %3d of %3d (%s) · differs %d · misses %d · adds %d · spans found %d of %d · "
              "%ss per product · cost %s" % (
                  r["extractor"], r["same_as_reference"], r["reference_figures"], r["agreement"], r["different_number"],
                  r["missing"], r["extra"], r["span_found"], r["figures_reported"], r["seconds_per_product_median"],
                  json.dumps(r["cost"])))
        if args.detail and r["extractor"] != result["reference"]:
            for d in r["differences"]:
                print("    %-16s %s | %s | reference %s | reader %s %s | %s" % (
                    d["kind"], d["store"], d["figure"], d["reference"], d["reader"],
                    "(unsure)" if d["reader_unsure"] else "", (d["reader_quote"] or d["reference_quote"] or "")[:80]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
