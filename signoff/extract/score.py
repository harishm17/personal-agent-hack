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


def dimension_check(row):
    return spans.position_check(row)


def item(key, row, titles):
    out = {"store": key[0], "product_id": key[1], "title": titles.get(key[:2]), "figure": key[2],
           "value": combine.shown(row), "quote": row["quote"]}
    position = dimension_check(row)
    if position:
        out["dimension"] = {"position": position["position"], "of": position["of"], "label": position["label"],
                            "expected": position["expected"], "ok": position["ok"]}
    return out


def measure(name, index, log, reference, titles, picks=None):
    counted = {k: r for k, r in index.items() if combine.counted(r)}
    ref = {k: r for k, r in reference.items() if combine.counted(r)}
    both = [k for k in ref if k in counted]
    same = [k for k in both if combine.same(ref[k], counted[k])]
    different = [k for k in both if not combine.same(ref[k], counted[k])]
    missing = [k for k in ref if k not in counted]
    extra = [k for k in counted if k not in ref]
    products = {(r["store"], r["product_id"]) for r in log if r.get("asked")}
    clean = products - {k[:2] for k in different + missing + extra}
    seconds = [r["seconds"] for r in log if r.get("seconds") is not None and r.get("asked")]
    wrong_position = [item(k, r, titles) for k, r in sorted(counted.items())
                      if (dimension_check(r) or {}).get("ok") is False]
    out = {
        "extractor": name, "products_read": len(products),
        "figures_reported": len(index),
        "span_found": sum(1 for r in index.values() if r.get("span_found_in_text")),
        "span_found_share": round(sum(1 for r in index.values() if r.get("span_found_in_text")) / len(index), 3) if index else None,
        "marked_unsure": sum(1 for r in index.values() if r.get("unsure")),
        "figures_counted": len(counted),
        # the honest reading: of the figures BOTH readers found, how many carry the same number
        "both_found": len(both), "same_number": len(same), "different_number": len(different),
        "only_reference_found": len(missing), "only_this_reader_found": len(extra),
        "agreement": round(len(same) / len(both), 3) if both else None,
        "statement": "same number on %d of %d figures both readers found; the reference alone found %d, this "
                     "reader alone found %d" % (len(same), len(both), len(missing), len(extra)),
        "disagreements": [dict(item(k, counted[k], titles), reference_value=combine.shown(ref[k]),
                               reference_quote=ref[k]["quote"]) for k in sorted(different)],
        "extra": [dict(item(k, counted[k], titles),
                       reference_says=(reference[k].get("unsure_reason") or "unsure") if k in reference else "not stated")
                  for k in sorted(extra)],
        "missing": [dict(item(k, ref[k], titles),
                         reader_says=(index[k].get("unsure_reason") or "unsure") if k in index else "not stated")
                    for k in sorted(missing)],
        "wrong_dimension_position": wrong_position,
        "picks_changed": picks,
        "products_fully_agreeing": len(clean),
        "seconds_per_product_median": round(statistics.median(seconds), 2) if seconds else None,
        "seconds_per_product_mean": round(statistics.mean(seconds), 2) if seconds else None,
        "cost": cost(log),
        # kept for readers of the first version of this file
        "reference_figures": len(ref), "same_as_reference": len(same), "missing_count": len(missing),
        "extra_count": len(extra),
    }
    return out


def picks_by_reader(runs, sheet_id="sheet1"):
    """{reader name: {line id: pick}} when that reader's figures decide, by the engine's own rules on the sheet
    as on disk. None when the sheet's inputs are not in this checkout."""
    try:
        from signoff.engine import rules
        from signoff.extract import run as runner
        sheet = json.loads((ROOT / "sheets" / (sheet_id + ".json")).read_text())
        files = runner.pool_files(sheet_id=sheet_id)
        pool = [p for f in files for p in json.loads(pathlib.Path(f).read_text())]
        answers_dir = (ROOT / "data" / "store_answers") if sheet_id == "sheet1" else (ROOT / "data" / sheet_id / "store_answers")
        answers = [a for f in sorted(answers_dir.glob("*.json")) for a in json.loads(f.read_text())] if answers_dir.is_dir() else []
        text = {(p["store"], p["product_id"]): p.get("text") for p in pool}
        out, status = {}, {}
        for name, index, _ in runs:
            rows = [dict(r, span_found_in_text=rules.span_found(r, text.get((r["store"], r["product_id"]))))
                    for r in index.values()]
            built = rules.build_state(json.loads(json.dumps(sheet)), pool, rows, answers, [], "comparison")
            out[name] = {l["line_id"]: next(({"store": c["product"]["store"], "title": c["product"]["title"],
                                              "price_cents": c["product"]["price_cents"],
                                              "sums": [k["expr"] for k in c["checks"]],
                                              "quotes": [t["quote"] for k in c["checks"] for t in k["terms"] if t.get("quote")]}
                                             for c in l["candidates"] if c["picked"]), None) for l in built["lines"]}
            status[name] = {c["id"]: {"line_id": l["line_id"], "store": c["product"]["store"], "title": c["product"]["title"],
                                      "price_cents": c["product"]["price_cents"], "status": c["status"],
                                      "reason": c["reason"], "sums": [k["expr"] for k in c["checks"]]}
                            for l in built["lines"] for c in l["candidates"]}
        return out, status
    except Exception:  # noqa: BLE001
        return None, None


def compare(figures=FIGURES, reference=None):
    figures = pathlib.Path(figures)
    runs = [load_run(f) for f in sorted((figures / "_runs").iterdir()) if f.is_dir()]
    if not runs:
        raise SystemExit("no reader runs under %s/_runs" % figures)
    first = [r for r in runs if "(second pass)" not in r[0]]
    ref = next((r for r in first if reference and reference in r[0]), None) or \
        next((r for r in first if "claude-sonnet" in r[0]), first[0])
    sheet_id = "sheet1" if figures.resolve() == FIGURES.resolve() else figures.name
    titles = {}
    try:
        from signoff.extract import run as runner
        for f in runner.pool_files(sheet_id=sheet_id):
            for p in json.loads(pathlib.Path(f).read_text()):
                titles[(p["store"], p["product_id"])] = p.get("title")
    except Exception:  # noqa: BLE001
        pass
    def one_pass(these, reference_index):
        """Every reader measured against the reference: once on the figures as read, once with the rule on."""
        picks, status = picks_by_reader(these, sheet_id)
        out = {}
        for name, index, log in these:
            changed, inside, inside_ref = None, None, None
            if picks and name != ref[0]:
                changed = [{"line_id": line, "with_reference": picks[ref[0]][line], "with_this_reader": mine}
                           for line, mine in picks[name].items()
                           if (mine or {}).get("title") != (picks[ref[0]][line] or {}).get("title")]
                inside = [dict(mine, with_reference=status[ref[0]][cid]["status"],
                               reference_reason=status[ref[0]][cid]["reason"])
                          for cid, mine in status[name].items()
                          if mine["status"] == "inside" and status[ref[0]][cid]["status"] != "inside"]
                inside_ref = [dict(theirs, with_this_reader=status[name][cid]["status"],
                                   this_reader_reason=status[name][cid]["reason"])
                              for cid, theirs in status[ref[0]].items()
                              if theirs["status"] == "inside" and status[name][cid]["status"] != "inside"]
            made = measure(name, index, log, reference_index, titles, changed)
            made["inside_only_with_this_reader"] = inside
            made["inside_only_with_reference"] = inside_ref
            out[name] = made
        return out

    def with_rule(index):
        fresh, caught = {}, []
        for key, row in index.items():
            row = dict(row)
            row.pop("dimension", None)
            if row.get("caught_by"):  # a record saved after the rule existed: undo it for the "before" pass
                row = dict(row)
            if spans.apply_position_rule(row):
                caught.append(key)
            fresh[key] = row
        return fresh, caught

    def as_read(index):
        out = {}
        for key, row in index.items():
            row = dict(row)
            if row.get("caught_by"):
                for k in ("unsure", "unsure_reason", "caught_by"):
                    row.pop(k, None)
            out[key] = row
        return out

    raw = [(name, as_read(index), log) for name, index, log in runs]
    ruled, caught = [], {}
    for name, index, log in raw:
        fresh, hit = with_rule(index)
        ruled.append((name, fresh, log))
        caught[name] = [item(k, index[k], titles) for k in hit]
    before = one_pass(raw, next(i for n, i, _ in raw if n == ref[0]))
    after = one_pass(ruled, next(i for n, i, _ in ruled if n == ref[0]))
    brief = lambda m: {  # noqa: E731
        "figures_counted": m["figures_counted"], "statement": m["statement"],
        "picks_changed": [p["line_id"] for p in m["picks_changed"] or []],
        "inside_only_with_this_reader": len(m["inside_only_with_this_reader"] or []),
        "inside_only_with_reference": len(m["inside_only_with_reference"] or []),
        "inside_only_with_this_reader_titles": [x["title"] for x in m["inside_only_with_this_reader"] or []]}
    readers = []
    for name, _, _ in runs:
        made = after[name]
        made["position_rule"] = {"rule": spans.POSITION_REASON, "caught": caught[name],
                                 "before": brief(before[name]), "after": brief(after[name])}
        made["wrong_dimension_position"] = caught[name]
        readers.append(made)
    readers.sort(key=lambda r: (r["extractor"] != ref[0], -(r["agreement"] or 0)))
    return {"made_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "position_rule": {
                "rule": "when a figure's quote is a labelled list of dimensions, its number must sit at the position "
                        "the store labels as that dimension; otherwise the figure is marked unsure and does not count",
                "reason_given": spans.POSITION_REASON, "applies_to": "every reader, in code",
                "caught": {r["extractor"]: r["position_rule"]["caught"] for r in readers if r["position_rule"]["caught"]},
                "reference_figures_caught": len(caught[ref[0]])},
            "reference": ref[0], "measure": "same number, on the figures both readers found, on the same products",
            "note": "Agreement, not accuracy: no person read these pages. A figure counts when its quote is "
                    "found in the store's text and the reader did not mark it unsure. Figures only one reader "
                    "found are listed separately, and so are the lines whose pick changes when that reader decides.",
            "products": len({(r["store"], r["product_id"]) for r in ref[2] if r.get("asked")}), "readers": readers}


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
        print("%-42s %s · spans found %d of %d · picks changed on %s · wrong dimension position %d · %ss per product · cost %s" % (
            r["extractor"], r["statement"], r["span_found"], r["figures_reported"],
            [p["line_id"] for p in r["picks_changed"]] if r["picks_changed"] is not None else "n/a",
            len(r["wrong_dimension_position"]), r["seconds_per_product_median"], json.dumps(r["cost"])))
        if r["extractor"] != result["reference"]:
            rule = r["position_rule"]
            print("      position rule: caught %s · inside only with this reader %d -> %d · picks changed %s -> %s" % (
                [(c["title"], c["value"]) for c in rule["caught"]], rule["before"]["inside_only_with_this_reader"],
                rule["after"]["inside_only_with_this_reader"], rule["before"]["picks_changed"], rule["after"]["picks_changed"]))
        if args.detail and r["extractor"] != result["reference"]:
            for d in r["disagreements"]:
                print("    differs  %s | %s | %s | reference %s %r | reader %s %r %s" % (
                    d["store"], (d["title"] or "")[:34], d["figure"], d["reference_value"], d["reference_quote"][:50],
                    d["value"], d["quote"][:50], d.get("dimension") or ""))
            for d in r["extra"]:
                print("    extra    %s | %s | %s | %s %r | reference: %s" % (
                    d["store"], (d["title"] or "")[:34], d["figure"], d["value"], d["quote"][:50], d["reference_says"][:70]))
            for d in r["picks_changed"] or []:
                print("    pick     %s | reference: %s | this reader: %s" % (
                    d["line_id"], d["with_reference"] and (d["with_reference"]["title"], d["with_reference"]["sums"]),
                    d["with_this_reader"] and (d["with_this_reader"]["title"], d["with_this_reader"]["sums"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
