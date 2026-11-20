"""A state for sheet 3 (a teacher's class supply list): headphones at most 85 dB, crayons exactly 24, a notebook of at
least 70 sheets, pencils at least 12 in a pack. Built with the engine's own rules from a small synthetic pool."""
import json

from signoff.engine import rules

from .standin import ROOT

STORES = ["purosound.com", "onanoff.com", "bazicproducts.com", "yoobi.com", "pencils.com"]
RAW = [
    ("C1", 0, 1999, [("max_volume", "single", 85, 85, "dB", "Volume limited to 85 dB.")]),
    ("C1", 1, 1299, [("max_volume", "single", 93, 93, "dB", "Peaks at 93 dB.")]),
    ("C2", 2, 150, [("crayon_count", "single", 24, 24, "count", "24 count box.")]),
    ("C2", 3, 100, [("crayon_count", "single", 16, 16, "count", "16 count box.")]),
    ("C3", 3, 349, [("sheet_count", "single", 70, 70, "sheets", "70 sheets.")]),
    ("C3", 2, 199, [("sheet_count", "single", 50, 50, "sheets", "50 sheets.")]),
    ("C4", 4, 275, [("pencil_count", "single", 12, 12, "count", "12 pack.")]),
    ("C4", 2, 99, [("pencil_count", "single", 10, 10, "count", "10 pack.")]),
]
FIGURE_NAMES = {"C1": "volume", "C2": "count", "C3": "sheets", "C4": "count"}
NOW = "2026-11-20T12:30:00-08:00"


def build(sheet_id="sheet3"):
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
