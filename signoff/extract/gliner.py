"""Superlinked SIE `extract` as a figure reader: a small entity model marks spans, code reads the number.

The model (GLiNER, pinned) returns labelled spans with character offsets. It does no arithmetic and gives
no unit or range: code parses those from the span's own characters, widened to the store's sentence around
it for the quote. The same `spans.finish` check judges the result as for every other reader.
"""
import re

from signoff import config
from signoff.engine import obs, rules
from signoff.extract import spans

MODEL = "urchade/gliner_multi-v2.1"
EXTRACTOR = "sie:" + MODEL
LABELS = {"weight_capacity": "weight capacity", "added_height": "added height", "seat_height": "seat height",
          "overall_width": "overall width", "length": "length", "mattress_thickness_max": "mattress thickness"}
# Words that must not sit just before a span for it to be this figure (a product's own weight is not its capacity).
NOT_BEFORE = {"weight_capacity": re.compile(r"(product|shipping|item|net|unit)\s+weight|weighs?\b", re.I),
              "overall_width": re.compile(r"(seat|inside|between)\b[^.]{0,20}$", re.I)}
UNIT = re.compile(r"\s*(lbs?\.?|pounds?|kgs?|inch(?:es)?|in\.|in\b|cm|mm|feet|ft|quarts?|qts?\.?|liters?|°\s?[FC]|\"|”|″)", re.I)
RANGE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:\"|”|″|inch(?:es)?|in\.?|lbs?\.?)?\s*(?:to|-|–|—)\s*(\d+(?:\.\d+)?)", re.I)

_client = None


def client():
    global _client
    if _client is None:
        from sie_sdk import SIEClient
        _client = SIEClient("https://api.superlinked.com", api_key=config.env("SIE_API_KEY"))
    return _client


def warm():
    """One small call so the pinned model is loaded before a batch or a demo (a cold model answers 503)."""
    client().extract(MODEL, {"text": "Weight capacity: 300 lbs. Overall width 20 inches."}, labels=list(LABELS.values())[:2])


def entities(text, names):
    labels = [LABELS.get(n, n.replace("_", " ")) for n in names]
    if not labels or not text:
        return []
    obs.egress("Superlinked SIE (%s)" % MODEL, "mark figure spans in one store page",
               {"text": text, "labels": labels}, ("store_text", "product"))
    return client().extract(MODEL, {"text": text}, labels=labels).get("entities") or []


def proposal(entity, name, text, target_unit=None):
    """A proposal from one entity, or None. The quote is the entity's span, widened to take in a unit or the
    second end of a range that sits right after it."""
    start, end = entity.get("start"), entity.get("end")
    if not isinstance(start, int) or not isinstance(end, int) or text[start:end] != entity.get("text"):
        return None
    blocker = NOT_BEFORE.get(name)
    if blocker and blocker.search(text[max(0, start - 30):start]):
        return None
    tail = text[end:end + 30]
    span = text[start:end]
    ranged = RANGE.match(text[start:end + 30]) if re.match(r"\s*(?:to|-|–|—)\s*\d", tail) else RANGE.search(span)
    if ranged and not RANGE.search(span):
        end = start + ranged.end()
        span, tail = text[start:end], text[end:end + 30]
    unit = UNIT.search(span)
    if not unit:
        after = UNIT.match(tail)
        if after:
            end += after.end()
            span = text[start:end]
            unit = UNIT.search(span)
    found = spans.numbers_in(span)
    if not found:
        return None
    out = {"figure": name, "stated": True, "quote": span, "unit": rules.unit_name(unit.group(1).lower().replace(" ", "")) if unit else None,
           "score": round(float(entity.get("score") or 0), 3), "entity_start": start, "entity_end": end}
    ranged = RANGE.search(span)
    if ranged:
        out.update(kind="adjustable", value=None, low=float(ranged.group(1)), high=float(ranged.group(2)))
    else:
        out.update(kind="single", value=found[-1] if len(found) == 1 else found[0], low=None, high=None)
    wanted = rules.FAMILY.get(rules.unit_name(target_unit)) if target_unit else (
        "weight" if name == "weight_capacity" else "length")
    if out["unit"] and wanted and rules.FAMILY.get(out["unit"]) != wanted:
        return None  # a width in pounds, a capacity in inches: not this figure
    return out


def read(product, sheet_names, units=None):
    """(proposals, extractor name, usage): the best-scoring usable entity for each figure asked for."""
    text = product.get("text") or ""
    by_label = {LABELS.get(n, n.replace("_", " ")): n for n in sheet_names}
    best = {}
    for entity in entities(text, sheet_names):
        name = by_label.get(entity.get("label"))
        made = proposal(entity, name, text, (units or {}).get(name)) if name in sheet_names else None
        if made and (name not in best or made["score"] > best[name]["score"]):
            best[name] = made
    return list(best.values()), EXTRACTOR, {"entities": True}
