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

from signoff.extract import combine, spans

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
    name = next((r["extractor"] for r in log if r.get("extractor") not in (None, "none")),
                rows[0]["extractor"] if rows else folder.name)
    if folder.name.endswith("-pass2"):
        name += " (second pass)"
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


def stated(rows):
    """{(store, product, variant, figure): the numbers the reader states there, with its quotes}."""
    out = {}
    for r in rows:
        if not r.get("span_found_in_text") or r.get("number_in_quote") is False:
            continue
        numbers = [r.get("value")] if r.get("kind") == "single" else [r.get("low"), r.get("high")]
        key = (r["store"], r["product_id"], r.get("variant_id"), r["figure"])
        out.setdefault(key, {"numbers": set(), "quotes": []})
        out[key]["numbers"].update(n for n in numbers if isinstance(n, (int, float)))
        out[key]["quotes"].append(r.get("quote"))
    return out


def built(rows, sheet, pool, answers):
    """A reader's figures run through the engine's own rules on the sheet as on disk: each candidate's status,
    each check's outcome, and each line's pick."""
    from signoff.engine import rules
    text = {(p["store"], p["product_id"]): p.get("text") for p in pool}
    ready = [spans.ready(dict(r), text.get((r["store"], r["product_id"]))) for r in rows]
    state = rules.build_state(json.loads(json.dumps(sheet)), pool, ready, answers, [], "comparison")
    checks, status, picks = {}, {}, {}
    for line in state["lines"]:
        pick = next((c for c in line["candidates"] if c["picked"]), None)
        picks[line["line_id"]] = pick and {"store": pick["product"]["store"], "title": pick["product"]["title"],
                                           "price_cents": pick["product"]["price_cents"],
                                           "sums": [k["expr"] for k in pick["checks"]],
                                           "quotes": [t["quote"] for k in pick["checks"] for t in k["terms"] if t.get("quote")]}
        for c in line["candidates"]:
            status[c["id"]] = {"line_id": line["line_id"], "store": c["product"]["store"], "title": c["product"]["title"],
                               "price_cents": c["product"]["price_cents"], "status": c["status"], "reason": c["reason"],
                               "sums": [k["expr"] for k in c["checks"]]}
            for k in c["checks"]:
                checks[(c["id"], k["limit_id"])] = k["state"]
    return {"checks": checks, "status": status, "picks": picks, "stated": stated(ready)}


def measure(name, rows, log, mine, ref, titles, is_reference):
    """One reader against the reference, after the rules: the outcomes of the same checks on the same candidates.
    Nothing is dropped: a check that is unclear or not stated for a reader is counted as that outcome."""
    pages = {(r["store"], r["product_id"], r.get("variant_id")) for r in log if r.get("asked")}
    seconds = [r["seconds"] for r in log if r.get("seconds") is not None and r.get("asked")]
    found = sum(1 for r in rows if r.get("span_found_in_text"))
    same = [k for k in ref["checks"] if mine["checks"].get(k) == ref["checks"][k]]
    table = {}
    for k, theirs in ref["checks"].items():
        pair = "%s -> %s" % (theirs, mine["checks"].get(k))
        table[pair] = table.get(pair, 0) + 1
    both = [k for k in ref["stated"] if k in mine["stated"]]
    differ = [k for k in both if ref["stated"][k]["numbers"] != mine["stated"][k]["numbers"]]

    def row(key, source):
        return {"store": key[0], "product_id": key[1], "title": titles.get(key[:2]), "figure": key[3],
                "values": sorted(source[key]["numbers"]), "quote": source[key]["quotes"][0]}

    def statuses(made):
        return {s: sum(1 for c in made["status"].values() if c["status"] == s)
                for s in ("inside", "outside", "unclear", "not_stated")}
    out = {
        "extractor": name, "pages_read": len(pages), "statements": len(rows), "span_found": found,
        "span_found_share": round(found / len(rows), 3) if rows else None,
        "candidates": statuses(mine),
        "checks_compared": len(ref["checks"]), "same_outcome": len(same),
        "outcomes": dict(sorted(table.items())),  # "what the reference found -> what this reader found": how many checks
        "statement": "same outcome on %d of %d checks (pass, fail, unclear or not stated, on the same candidates)" % (
            len(same), len(ref["checks"])),
        "figures_both_state": len(both), "same_numbers": len(both) - len(differ),
        "only_reference_states": sum(1 for k in ref["stated"] if k not in mine["stated"]),
        "only_this_reader_states": sum(1 for k in mine["stated"] if k not in ref["stated"]),
        "disagreements": [dict(row(k, mine), reference_values=sorted(ref["stated"][k]["numbers"]),
                               reference_quote=ref["stated"][k]["quotes"][0]) for k in sorted(differ, key=str)],
        "extra": [row(k, mine) for k in sorted((k for k in mine["stated"] if k not in ref["stated"]), key=str)],
        "picks_changed": None if is_reference else [
            {"line_id": line, "with_reference": ref["picks"][line], "with_this_reader": pick}
            for line, pick in mine["picks"].items() if (pick or {}).get("title") != (ref["picks"][line] or {}).get("title")],
        "inside_only_with_this_reader": None if is_reference else [
            dict(c, with_reference=ref["status"][cid]["status"], reference_reason=ref["status"][cid]["reason"])
            for cid, c in mine["status"].items() if c["status"] == "inside" and ref["status"][cid]["status"] != "inside"],
        "inside_only_with_reference": None if is_reference else [
            dict(c, with_this_reader=mine["status"][cid]["status"], this_reader_reason=mine["status"][cid]["reason"])
            for cid, c in ref["status"].items() if c["status"] == "inside" and mine["status"][cid]["status"] != "inside"],
        "seconds_per_page_median": round(statistics.median(seconds), 2) if seconds else None,
        "cost": cost(log),
    }
    out["seconds_per_product_median"] = out["seconds_per_page_median"]  # the earlier name, kept
    return out


def inputs(figures):
    """(sheet id, sheet, pool rows, store answers) of the sheet whose figure folder this is."""
    from signoff.extract import run as runner
    figures = pathlib.Path(figures)
    sheet_id = next((p.stem for p in sorted((ROOT / "sheets").glob("*.json"))
                     if runner.sheet_dirs(p.stem)[1].resolve() == figures.resolve()), None)
    if sheet_id is None:
        return None, None, [], []
    sheet = json.loads((ROOT / "sheets" / (sheet_id + ".json")).read_text())
    pool = runner.rows_of(runner.pool_files(sheet_id=sheet_id))
    answers_dir = runner.sheet_dirs(sheet_id)[0].parent / "store_answers"
    answers = [a for f in sorted(answers_dir.glob("*.json")) for a in json.loads(f.read_text())] if answers_dir.is_dir() else []
    return sheet_id, sheet, pool, answers


def compare(figures=FIGURES, reference=None, sheet_inputs=None):
    figures = pathlib.Path(figures)
    runs = []
    for folder in sorted((figures / "_runs").iterdir()):
        if folder.is_dir():
            name, _, log = load_run(folder)
            rows = [r for f in sorted(folder.glob("*.json")) for r in json.loads(f.read_text())]
            runs.append((name, rows, log))
    if not runs:
        raise SystemExit("no reader runs under %s/_runs" % figures)
    first = [r for r in runs if "(second pass)" not in r[0]]
    ref = next((r for r in first if reference and reference in r[0]), None) or \
        next((r for r in first if "claude-sonnet" in r[0]), first[0])
    sheet_id, sheet, pool, answers = sheet_inputs or inputs(figures)
    if sheet is None:
        raise SystemExit("%s is not the figure folder of a sheet in sheets/" % figures)
    titles = {(p["store"], p["product_id"]): p.get("title") for p in pool}
    made = {name: built(rows, sheet, pool, answers) for name, rows, _ in runs}
    readers = [measure(name, rows, log, made[name], made[ref[0]], titles, name == ref[0]) for name, rows, log in runs]
    readers.sort(key=lambda r: (r["extractor"] != ref[0], -r["same_outcome"]))
    return {"made_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "sheet_id": sheet_id,
            "reference": ref[0],
            "measure": "the outcome of every check (pass, fail, unclear, not stated) on the same candidates, after the rules",
            "note": "Agreement with the reference reader, not accuracy: no person read every page. Nothing is dropped "
                    "from the count: a check that is unclear or not stated for a reader is counted as that outcome.",
            "pages": len(pool), "readers": readers}


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
    print("sheet %s · reference %s · %d pages · %s" % (result["sheet_id"], result["reference"], result["pages"], result["measure"]))
    for r in result["readers"]:
        print("%-42s %s · candidates %s · picks changed on %s · %s s per page · cost %s" % (
            r["extractor"], r["statement"], r["candidates"],
            [p["line_id"] for p in r["picks_changed"]] if r["picks_changed"] is not None else "n/a",
            r["seconds_per_page_median"], json.dumps(r["cost"])))
        if args.detail and r["picks_changed"] is not None:
            print("      outcomes (reference -> this reader):", r["outcomes"])
            for d in r["disagreements"]:
                print("    differs  %s | %s | %s | reference %s %r | reader %s %r" % (
                    d["store"], (d["title"] or "")[:34], d["figure"], d["reference_values"], (d["reference_quote"] or "")[:50],
                    d["values"], (d["quote"] or "")[:50]))
            for d in r["picks_changed"]:
                print("    pick     %s | reference: %s | this reader: %s" % (
                    d["line_id"], d["with_reference"] and (d["with_reference"]["title"], d["with_reference"]["sums"]),
                    d["with_this_reader"] and (d["with_this_reader"]["title"], d["with_this_reader"]["sums"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
