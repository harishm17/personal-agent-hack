"""A state for sheet 2 (the plumber's fixture list) built with the engine's own rules from a small synthetic pool of
four stores, so tests of SIGN run on the second sheet's shape: names, lines T1 to T4, units gpf and gpm, an `==` limit."""
import json

from signoff.engine import rules

from .standin import ROOT

STORES = ["swissmadison.com", "horow.com", "deervalleybath.com", "kingstonbrass.com"]
# line, store index, price cents, [(figure, kind, low, high, unit, sentence)]
RAW = [
    ("T1", 0, 24900, [("rough_in", "single", 10, 10, "in", "Rough-in: 10 in."), ("flush_volume", "single", 1.28, 1.28, "gpf", "Flush volume 1.28 gpf.")]),
    ("T1", 1, 34900, [("rough_in", "single", 10, 10, "in", "10 inch rough-in."), ("flush_volume", "single", 1.1, 1.1, "gpf", "Uses 1.1 gpf.")]),
    ("T2", 2, 8900, [("flow_rate", "single", 1.2, 1.2, "gpm", "Flow rate 1.2 gpm.")]),
    ("T2", 3, 12900, [("flow_rate", "single", 1.2, 1.2, "gpm", "Max flow 1.2 gpm.")]),
    ("T3", 1, 6900, [("flow_rate", "single", 1.8, 1.8, "gpm", "Flow rate 1.8 gpm.")]),
    ("T3", 3, 9900, [("flow_rate", "single", 1.75, 1.75, "gpm", "1.75 gpm.")]),
    ("T4", 2, 39900, [("overall_width", "single", 30.0, 30.0, "in", "Overall width 30 in.")]),
    ("T4", 0, 54900, [("overall_width", "single", 29.0, 29.0, "in", "Width: 29 inches.")]),
]
NOW = "2026-11-20T12:30:00-08:00"


def build():
    sheet = json.loads((ROOT / "sheets" / "sheet2.json").read_text())
    pool, figures = [], []
    for i, (line, si, price, parts) in enumerate(RAW):
        text, spans = "Product %d. " % i, []
        for part in parts:
            spans.append((part, len(text), len(text) + len(part[5])))
            text += part[5] + " "
        pid = "p%d" % i
        pool.append({"store": STORES[si], "product_id": pid, "variant_id": "gid://v/%s" % pid, "title": "Fixture %s %d" % (line, i),
                     "price_cents": price, "url": "https://%s/p/%s" % (STORES[si], pid), "text": text.strip(), "fetched_at": NOW,
                     "product_key": "fixture %d" % i, "line_ids": [line]})
        for (fig, kind, low, high, unit, sentence), start, end in spans:
            figures.append({"store": STORES[si], "product_id": pid, "figure": fig, "kind": kind, "value": low if kind == "single" else None,
                            "low": low, "high": high, "unit": unit, "quote": sentence, "start": start, "end": end,
                            "extractor": "test", "span_found_in_text": text[start:end] == sentence})
    answers = [{"store": s, "asked_at": NOW, "question": "q", "answer": "a", "delivery": {"stated": True, "quote": "Ships in 3 to 5 days", "days_low": 3, "days_high": 5},
                "returns": {"returnable": "yes", "fee": None, "quote": "Returns within 30 days", "applies_to": "all"}} for s in STORES]
    keep = rules.unit_name
    rules.unit_name = lambda u: u if u else None   # gpf and gpm are ENGINE's to add; the shape is what these tests need
    try:
        return rules.build_state(sheet, pool, figures, answers, [], "fixture")
    finally:
        rules.unit_name = keep
