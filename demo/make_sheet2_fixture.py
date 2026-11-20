"""Writes web/screen/fixture-sheet2.json: sheets/sheet2.json run over placeholder products (no real brand, no real
store text), so the screen can be built for sheet 2 before the engine serves it. Drawn with /?fixture=sheet2.

The decision records come from fixtures/make_state.py; the checks, picks and counts are then worked out again by
web/screen/model.js `simulate` (it knows the `==` op and the pick rule by id, which the reference code does not).

Run: uv run python demo/make_sheet2_fixture.py
"""
import importlib.util
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("make_state", ROOT / "fixtures" / "make_state.py")
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

NOW = "2026-11-20T12:50:00-08:00"
STORES = ["fixture-store-a.example", "fixture-store-b.example", "fixture-store-c.example", "fixture-store-d.example"]


def one(fig, v, unit, text):
    return (fig, "single", v, v, unit, text)


def spread(fig, lo, hi, unit, text):
    return (fig, "spread", lo, hi, unit, text)


RI = lambda v: one("rough_in", v, "in", "Rough-in: %g inches." % v)
FL = lambda v: one("flush_volume", v, "gpf", "Flush volume %g GPF." % v)
DF = lambda lo, hi: spread("flush_volume", lo, hi, "gpf", "Dual flush: %g to %g GPF." % (lo, hi))
FR = lambda v: one("flow_rate", v, "gpm", "Flow rate: %g GPM." % v)
OW = lambda v: one("overall_width", v, "in", "Overall width: %g inches." % v)

# line, store index, price cents, sentences
RAW = [
    ("T1", 0, 34900, [RI(10), DF(0.8, 1.28)]), ("T1", 0, 29900, [RI(12), DF(0.8, 1.28)]), ("T1", 0, 27900, [RI(10), DF(1.1, 1.6)]),
    ("T1", 0, 38900, [RI(10), FL(1.28)]), ("T1", 0, 25900, [RI(12), FL(1.28)]), ("T1", 1, 36900, [RI(10), FL(1.28)]),
    ("T1", 1, 41900, [RI(10), FL(1.0)]), ("T1", 1, 23900, [RI(12), FL(1.6)]), ("T1", 1, 31900, [FL(1.28), "Fits most bathrooms."]),
    ("T1", 2, 45900, [RI(10), FL(0.8)]), ("T1", 2, 28900, [RI(14), FL(1.28)]), ("T1", 2, 26900, [RI(12), "Powerful siphon flush."]),
    ("T1", 2, 33900, [RI(10), DF(1.1, 1.6)]), ("T1", 3, 52900, [RI(10), FL(1.28)]), ("T1", 3, 30900, ["Elongated bowl.", "Soft-close seat."]),
    ("T2", 0, 8900, [FR(1.2)]), ("T2", 1, 7400, [FR(1.2)]), ("T2", 1, 6900, [FR(1.5)]), ("T2", 2, 11900, [FR(1.2)]),
    ("T2", 3, 15900, [FR(1.2)]), ("T2", 3, 9900, ["Solid brass body."]),
    ("T3", 0, 5900, [FR(2.5)]), ("T3", 0, 7900, [FR(1.8)]), ("T3", 1, 4900, [FR(2.5)]), ("T3", 1, 6900, [FR(1.8)]),
    ("T3", 2, 9900, [FR(1.8)]), ("T3", 3, 12900, [FR(1.5)]), ("T3", 3, 8900, ["Rainfall spray."]),
    ("T4", 0, 45900, [OW(30)]), ("T4", 0, 39900, ["30 inch vanity.", "Soft-close doors."]), ("T4", 1, 42900, [OW(30.5)]),
    ("T4", 1, 36900, [OW(24)]), ("T4", 2, 51900, [OW(29.5)]), ("T4", 2, 55900, [OW(36)]), ("T4", 3, 47900, ["Solid wood frame."]),
    ("T4", 3, 61900, [OW(30)]),
]
ANSWERS = [{"store": s, "asked_at": NOW, "question": "How long does delivery take, and can an opened item be returned?",
            "answer": "Fixture reply: %s Returns within 30 days if unopened." % ("we do not state delivery times." if i == 1 else "ground shipping takes 3 to 7 days."),
            "delivery": {"stated": i != 1, "quote": None if i == 1 else "ground shipping takes 3 to 7 days",
                         "days_low": None if i == 1 else 3, "days_high": None if i == 1 else 7},
            "returns": {"returnable": "unclear", "fee": None, "quote": "Returns within 30 days if unopened", "applies_to": "all"}}
           for i, s in enumerate(STORES)]


def build(sheet_id, raw_rows, stores, prefix):
    sheet = json.loads((ROOT / "sheets" / (sheet_id + ".json")).read_text())
    sheet["stores"] = stores
    sheet.setdefault("shopper_facts", [])
    pool, figures = [], []
    for n, (line_id, si, price, parts) in enumerate(raw_rows):
        pid = "%s-%02d" % (prefix, n + 1)
        text, spans = "Fixture product %s. " % pid, []
        for part in parts:
            sentence = part if isinstance(part, str) else part[5]
            if not isinstance(part, str):
                spans.append((part, len(text), len(text) + len(sentence)))
            text += sentence + " "
        pool.append({"store": stores[si], "product_id": pid, "variant_id": pid + "-v1", "title": "Fixture product " + pid,
                     "price_cents": price, "url": "https://%s/products/%s" % (stores[si], pid), "text": text.strip(),
                     "fetched_at": NOW, "product_key": "fixture " + pid, "line_ids": [line_id]})
        for (fig, kind, low, high, unit, sentence), start, end in spans:
            figures.append({"store": stores[si], "product_id": pid, "figure": fig, "kind": kind,
                            "value": low if kind == "single" else None, "low": low, "high": high, "unit": unit,
                            "quote": sentence, "start": start, "end": end, "extractor": "fixture",
                            "span_found_in_text": text[start:end] == sentence})
    answers = [dict(ANSWERS[i % len(ANSWERS)], store=st) for i, st in enumerate(stores)]
    state = ms.build_state(sheet, pool, figures, answers, [])
    for line, sheet_line in zip(state["lines"], sheet["lines"]):
        if sheet_line.get("quantity"):
            line["quantity"] = sheet_line["quantity"]
    raw = ROOT / "web" / "screen" / ("fixture-%s.json" % sheet_id)
    raw.write_text(json.dumps(state))
    script = ("import {readFileSync, writeFileSync} from 'node:fs'; import {simulate} from './web/screen/model.js';"
              "const p='web/screen/fixture-%s.json'; const s=simulate(JSON.parse(readFileSync(p)));" % sheet_id +
              "writeFileSync(p, JSON.stringify(s, null, 1) + '\\n');"
              "for (const l of s.lines) console.log(l.line_id, l.need, '|', l.status, '|', l.pick, '|', l.tightest && l.tightest.text, '|', JSON.stringify(l.why));"
              "console.log(JSON.stringify(s.counts), s.total_cents);")
    subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT, check=True)
    return raw


def main():
    raw = build("sheet2", RAW, STORES, "fx2")
    # Shapes the reference code does not make, added by hand so the screen can be looked at: a page that states the
    # figure but not one clear value (status `unclear`), and one product sold in two options (two rows, one name).
    state = json.loads(raw.read_text())
    t1 = next(l for l in state["lines"] if l["line_id"] == "T1")
    by = {c["product"]["product_id"]: c for c in t1["candidates"]}
    u = by["fx2-11"]
    u["status"], u["reason"] = "unclear", "rough in stated, but not clearly for this product: the page states both 10 and 12 in"
    u["checks"][0].update({"state": "unclear", "pass": False, "lhs": None, "margin": None, "expr": None})
    u["checks"][0]["terms"][0].update({"values": [10, 12], "quote": "Available in 10 or 12 inch rough-in."})
    for pid, option in (("fx2-01", "10 in rough-in"), ("fx2-02", "12 in rough-in")):
        by[pid]["product"]["title"] = "Fixture product fx2-01"
        by[pid]["product"]["variant_title"] = option
    raw.write_text(json.dumps(state, indent=1) + "\n")


    sheet3()


# Sheet 3, the teacher's list: one limit an item, a quantity of 24, units dB, count and sheets.
DB = lambda v: one("max_volume", v, "dB", "Volume limited to %g dB." % v)
CR = lambda v: one("crayon_count", v, "count", "%g crayons in the box." % v)
SH = lambda v: one("sheet_count", v, "sheets", "%g sheets, wide ruled." % v)
PE = lambda v: one("pencil_count", v, "count", "Pack of %g pencils." % v)
RAW3 = [
    ("C1", 0, 1499, ["Wired headphones for kids."]), ("C1", 1, 1799, [DB(94)]), ("C1", 2, 1999, [DB(85)]), ("C1", 0, 2499, [DB(85)]),
    ("C1", 3, 2999, [DB(75)]), ("C1", 1, 3499, [DB(85)]), ("C1", 4, 1299, [DB(95)]),
    ("C2", 0, 149, [CR(16)]), ("C2", 1, 179, [CR(64)]), ("C2", 2, 199, [CR(24)]), ("C2", 3, 249, [CR(24)]), ("C2", 4, 129, ["Bright colours."]),
    ("C3", 0, 99, [SH(50)]), ("C3", 1, 129, ["One subject notebook."]), ("C3", 2, 149, [SH(70)]), ("C3", 3, 189, [SH(100)]), ("C3", 4, 139, [SH(60)]),
    ("C4", 0, 199, [PE(10)]), ("C4", 1, 249, [PE(12)]), ("C4", 2, 299, [PE(24)]), ("C4", 3, 179, ["Pre-sharpened."]),
]


def sheet3():
    stores = ["fixture-store-%s.example" % c for c in "abcde"]
    raw = build("sheet3", RAW3, stores, "fx3")
    # by hand: a page that states several levels fails on the loudest (the sheet says `several: largest`)
    state = json.loads(raw.read_text())
    c1 = next(l for l in state["lines"] if l["line_id"] == "C1")
    m = next(c for c in c1["candidates"] if c["product"]["product_id"] == "fx3-02")
    m["checks"][0]["terms"][0].update({"values": [75, 85, 94], "quote": "Three sound levels: 75dB, 85dB, or 94dB."})
    raw.write_text(json.dumps(state, indent=1) + "\n")


if __name__ == "__main__":
    main()
