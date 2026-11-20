"""A state for sheet 4, "Home after surgery, short": shower chair, walker, grab bar with sheet 1's line and limit ids.
Built with the engine's own rules from a small synthetic pool."""
import json

from signoff.engine import rules

from .standin import ROOT

STORES = ["carex.com", "vivehealth.com", "parentgiving.com"]
RAW = [
    ("L1", 0, 7538, [("weight_capacity", "single", 500, 500, "lb", "Holds up to 500 lb."), ("overall_width", "single", 20.0, 20.0, "in", "Overall width 20 inches.")]),
    ("L1", 1, 5499, [("weight_capacity", "single", 300, 300, "lb", "Supports 300 lb."), ("overall_width", "single", 23.0, 23.0, "in", "Overall width 23 inches.")]),
    ("L1", 2, 4199, [("weight_capacity", "single", 350, 350, "lb", "Rated for 350 lb."), ("overall_width", "single", 17.0, 17.0, "in", "Width (outside legs): 17 in.")]),
    ("L4", 0, 4471, [("weight_capacity", "single", 350, 350, "lb", "Supports 350 lb."), ("overall_width", "single", 27.5, 27.5, "in", "Overall width 27.5 inches.")]),
    ("L4", 2, 5999, [("weight_capacity", "single", 300, 300, "lb", "Supports 300 lb."), ("overall_width", "single", 29.0, 29.0, "in", "Overall width 29 inches.")]),
    ("L5", 1, 1899, [("weight_capacity", "single", 500, 500, "lb", "Supports 500 lb."), ("length", "single", 18.0, 18.0, "in", "Length 18 inches.")]),
    ("L5", 2, 2499, [("weight_capacity", "single", 250, 250, "lb", "Holds 250 lb."), ("length", "single", 24.0, 24.0, "in", "Length 24 inches.")]),
]
NOW = "2026-11-20T12:30:00-08:00"


def build(sheet_id="sheet4"):
    sheet = json.loads((ROOT / "sheets" / (sheet_id + ".json")).read_text())
    pool, figures = [], []
    for i, (line, si, price, parts) in enumerate(RAW):
        text, spans = "Product %d. " % i, []
        for part in parts:
            spans.append((part, len(text), len(text) + len(part[5])))
            text += part[5] + " "
        pid = "p%d" % i
        pool.append({"store": STORES[si], "product_id": pid, "variant_id": "gid://v/%s" % pid, "title": "Supply %s %d" % (line, i),
                     "price_cents": price, "url": "https://%s/p/%s" % (STORES[si], pid), "text": text.strip(), "fetched_at": NOW,
                     "product_key": "supply %d" % i, "line_ids": [line]})
        for (fig, kind, low, high, unit, sentence), start, end in spans:
            figures.append({"store": STORES[si], "product_id": pid, "figure": fig, "kind": kind, "value": low,
                            "low": low, "high": high, "unit": unit, "quote": sentence, "start": start, "end": end,
                            "extractor": "test", "span_found_in_text": text[start:end] == sentence})
    answers = [{"store": s, "asked_at": NOW, "question": "q", "answer": "a", "delivery": {"stated": True, "quote": "Ships in 3 to 5 days", "days_low": 3, "days_high": 5},
                "returns": {"returnable": "yes", "fee": None, "quote": "Returns within 30 days", "applies_to": "all"}} for s in STORES]
    keep = rules.unit_name
    rules.unit_name = lambda u: u if u else None
    try:
        return rules.build_state(sheet, pool, figures, answers, [], "fixture")
    finally:
        rules.unit_name = keep
