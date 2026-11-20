"""The guard on what is shared with another agent. A model may draft a message; this code decides what leaves.

The rule is data: a sheet's `sharing` says which kinds of fact each kind of recipient may receive; a kind that is not
listed is sealed for that recipient. The check on a message has two parts:
  (a) the active sheet's own values of every sealed kind, found by normalised match (a limit or a home measurement as a
      number, in digits or words, with or without its unit; a person's name or role);
  (b) spans about health, a person, money and an address, found by a small span model. The model only marks spans; code
      checks each span's offsets and score, and decides.
A span that lies inside a fact the recipient may receive (the store's own product title, the need-by date, the region)
is not counted. Anything else is cut from the message.
"""
import datetime
import re

from signoff.obs import _egress_module as ledger  # the ledger module (`signoff.obs.egress` itself is the function)

KINDS = ("product", "need_by", "delivery_region", "limit", "home_measurement", "person", "health", "money", "address")
DEFAULT = {"store": ["product", "need_by", "delivery_region"]}
MARK = {"limit": "order limit", "home_measurement": "home measurement", "person": "a person", "health": "health detail",
        "money": "money amount", "address": "home address", "need_by": "need-by date", "delivery_region": "delivery region",
        "product": "product name"}
SPAN_MODEL = "urchade/gliner_multi-v2.1"
SPAN_LABELS = {"person name": "person", "family member": "person", "job title": "person",
               "health condition": "health", "medical procedure": "health", "body weight": "health",
               "amount of money": "money", "street address": "address"}
MIN_SCORE = 0.5
GAP = "[…]"

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
         "eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def allowed(sheet: dict, recipient_kind: str = "store") -> set:
    """The kinds of fact this kind of recipient may receive: the sheet's `sharing`, else the default."""
    rule = sheet.get("sharing") or DEFAULT
    return {k for k in rule.get(recipient_kind, []) if k in KINDS}


def rule(sheet: dict, recipient_kind: str = "store") -> dict:
    may = allowed(sheet, recipient_kind)
    return {"recipient": recipient_kind, "may": [k for k in KINDS if k in may], "sealed": [k for k in KINDS if k not in may],
            "source": "sheet" if sheet.get("sharing") else "default"}


def _words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("-" + _ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return _ONES[n // 100] + " hundred" + (" " + _words(n % 100) if n % 100 else "")
    return _words(n // 1000) + " thousand" + (" " + _words(n % 1000) if n % 1000 else "")


def _number_forms(v: float) -> str:
    """One pattern for the ways a number can be written: digits (300, 300.0, 21.5, 21 1/2, 21½) and words."""
    whole, half = int(v), (v % 1 == 0.5)
    forms = []
    if float(v).is_integer():
        forms.append(rf"{whole}(?:\.0+)?")
    else:
        forms.append(re.escape(repr(float(v))))
    if half:
        forms += [rf"{whole}\s*(?:1/2|½)", re.sub(r"[ -]", r"[\\s-]+", _words(whole)) + r"[\s-]+and[\s-]+a[\s-]+half\b"]
    elif float(v).is_integer() and 0 <= whole < 1_000_000:
        forms.append(re.sub(r"[ -]", r"[\\s-]+", _words(whole)).replace("hundred[\\s-]+", "hundred[\\s-]+(?:and[\\s-]+)?") + r"\b")
    return r"(?<![\w.,/-])(?:" + "|".join(forms) + r")(?![\d/]|[.,]\d)"


def _unit_forms(unit: str, sheet: dict) -> str:
    alts = [ledger.UNITS[unit]] if unit in ledger.UNITS else []
    alts += [re.escape(a) + r"\b" for a in (sheet.get("units") or {}).get(unit, [])]
    if not alts and unit:
        alts.append(re.escape(unit) + r"\b")
    return r"(?:\s*-?\s*(?:" + "|".join(alts) + r"))?" if alts else ""


def _dates(iso: str) -> list:
    """The ways the need-by date is written."""
    try:
        d = datetime.date.fromisoformat(iso)
    except (TypeError, ValueError):
        return [iso] if iso else []
    return [iso, d.strftime("%B %-d, %Y"), d.strftime("%B %-d"), d.strftime("%b %-d, %Y"), d.strftime("%b %-d"),
            d.strftime("%-m/%-d/%Y"), d.strftime("%m/%d/%Y"), d.strftime("%-d %B %Y"), d.strftime("%-d %B")]


def need_by_text(sheet: dict) -> str | None:
    """The need-by date as the agent writes it."""
    forms = _dates(sheet.get("need_by"))
    return forms[1] if len(forms) > 1 else (forms[0] if forms else None)


def facts(sheet: dict, product: dict | None = None) -> dict:
    """The sheet's values by kind. Text kinds are lists of strings; number kinds are (value, unit, id) triples."""
    out = {k: [] for k in KINDS}
    if product and product.get("title"):
        out["product"].append(product["title"])
    out["need_by"] = _dates(sheet.get("need_by"))
    if sheet.get("delivery_region"):
        out["delivery_region"].append(sheet["delivery_region"])
    for f in sheet.get("shopper_facts", []):
        out["home_measurement"].append((float(f["value"]), f.get("unit", ""), f["id"]))
    for line in sheet.get("lines", []):
        for lim in line.get("limits", []):
            b = lim.get("bound", {})
            if b.get("source") == "issuer":
                out["limit"].append((float(b["value"]), lim.get("unit", ""), lim["id"]))
    for who in ("issuer", "shopper"):
        p = sheet.get(who) or {}
        out["person"] += [t for t in re.findall(r"[^\W\d_]{3,}", p.get("name") or "")]
        out["person"] += [r.strip() for r in (p.get("role"), (p.get("role_label") or "").split(",")[0]) if r and r.strip()]
    return out


def _free(text: str, strings: list) -> list:
    """Where the recipient's permitted facts sit in the text: (start, end) intervals."""
    out = []
    for s in strings:
        if s:
            out += [(m.start(), m.end()) for m in re.finditer(re.escape(s), text, re.I)]
    return out


def sheet_spans(text: str, sheet: dict, product: dict | None = None, recipient_kind: str = "store") -> list:
    """(a) the sheet's sealed values in the text, by normalised match."""
    may, known, found = allowed(sheet, recipient_kind), facts(sheet, product), []
    for kind in KINDS:
        if kind in may:
            continue
        for item in known[kind]:
            if isinstance(item, tuple):
                value, unit, fact_id = item
                pattern, what = _number_forms(value) + _unit_forms(unit, sheet), fact_id
            else:
                pattern, what = r"(?<!\w)" + re.escape(item) + r"(?!\w)", kind
            for m in re.finditer(pattern, text, re.I):
                found.append({"start": m.start(), "end": m.end(), "text": m.group(0), "kind": kind, "mark": MARK[kind],
                              "by": "sheet value", "rule": "%s is sealed for a %s (%s)" % (MARK[kind], recipient_kind, what)})
    return found


def sie_finder(text: str, labels: list) -> list:
    """The span model (Superlinked SIE, GLiNER). Returns its entities as they come; `model_spans` checks them."""
    from signoff import obs
    from signoff.extract import gliner
    obs.egress("sie:" + SPAN_MODEL, "talk: mark health, person, money and address spans in an outbound draft",
               {"text": text, "labels": labels}, ("person",))
    return gliner.client().extract(SPAN_MODEL, {"text": text}, labels=labels).get("entities") or []


def model_spans(text: str, sheet: dict, finder, recipient_kind: str = "store") -> list:
    """(b) spans a model marked. Code keeps a span only when its offsets are real, its score is high enough and its
    kind is sealed for this recipient."""
    may = allowed(sheet, recipient_kind)
    labels = [label for label, kind in SPAN_LABELS.items() if kind not in may]
    if not labels or not text.strip():
        return []
    found = []
    for e in finder(text, labels):
        start, end, kind = e.get("start"), e.get("end"), SPAN_LABELS.get(e.get("label"))
        if not isinstance(start, int) or not isinstance(end, int) or text[start:end] != e.get("text") or not kind:
            continue
        if kind in may or float(e.get("score") or 0) < MIN_SCORE:
            continue
        found.append({"start": start, "end": end, "text": text[start:end], "kind": kind, "mark": MARK[kind],
                      "by": "span model", "score": round(float(e["score"]), 2),
                      "rule": "%s is sealed for a %s (%s)" % (MARK[kind], recipient_kind, e["label"])})
    return found


def check(text: str, sheet: dict, product: dict | None = None, finder=sie_finder, recipient_kind: str = "store") -> list:
    """Every sealed span in an outbound message, in order, without overlaps. An empty list means the message may leave."""
    may, known = allowed(sheet, recipient_kind), facts(sheet, product)
    free = _free(text, [s for k in may for s in known[k] if isinstance(s, str)])
    spans = sheet_spans(text, sheet, product, recipient_kind) + model_spans(text, sheet, finder, recipient_kind)
    spans = [s for s in spans if not any(a <= s["start"] and s["end"] <= b for a, b in free)]
    spans.sort(key=lambda s: (s["start"], s["by"] != "sheet value", -(s["end"] - s["start"])))
    out = []
    for s in spans:
        if out and s["start"] < out[-1]["end"]:  # overlap: one span, the wider end, the first rule
            if s["end"] > out[-1]["end"]:
                out[-1]["end"] = s["end"]
                out[-1]["text"] = text[out[-1]["start"]:s["end"]]
            continue
        out.append(dict(s))
    return out


def cut(text: str, spans: list) -> str:
    """The message with every sealed span taken out and a gap mark left in its place."""
    out, at = [], 0
    for s in sorted(spans, key=lambda s: s["start"]):
        out.append(text[at:s["start"]])
        out.append(GAP)
        at = max(at, s["end"])
    out.append(text[at:])
    return re.sub(r"[ \t]{2,}", " ", "".join(out)).strip()


def gaps(text: str) -> list:
    """A gap mark left in a rewritten message: the message is not whole, so it does not leave."""
    return [{"start": m.start(), "end": m.end(), "text": m.group(0), "kind": "gap", "mark": "gap mark", "by": "code",
             "rule": "a message with a gap mark in it is not sent"} for m in re.finditer(r"\[\s*(?:…|\.{3})\s*\]", text)]
