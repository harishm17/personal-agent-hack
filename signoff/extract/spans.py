"""Code's half of reading a figure: find the quote in the store's text, and check the numbers are in it.

The model proposes; nothing it says about offsets is used. A proposal becomes a figure record only through
`finish`, and a record whose span is not found does not count anywhere downstream.
"""
import re

from signoff.engine import rules

FOLD = {"“": '"', "”": '"', "″": '"', "‘": "'", "’": "'", "′": "'", "–": "-", "—": "-", "‑": "-",
        " ": " ", " ": " ", " ": " ", "×": "x"}
FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3, "⅛": 0.125, "⅜": 0.375, "⅝": 0.625, "⅞": 0.875}
NUMBER = re.compile(r"(?<![\w.])(\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)")
MIXED = re.compile(r"(?<![\w./])(\d+)[ -](\d+)/(\d+)(?![\w/])")
FRACTION = re.compile(r"(?<![\w./])(\d+)/(\d+)(?![\w/])")


def _folded(text):
    """Text with whitespace runs as one space and typographic marks as plain ones, plus an index back."""
    out, index, space = [], [], False
    for i, ch in enumerate(text):
        ch = FOLD.get(ch, ch)
        if ch.isspace():
            if not space and out:
                out.append(" ")
                index.append(i)
            space = True
            continue
        space = False
        out.append(ch.lower())
        index.append(i)
    return "".join(out), index


def locate(quote, text):
    """(start, end, how) of the quote in the text, or None. `how` is `exact` or `normalised`.

    The normalised pass forgives spacing, letter case and curly marks only; the span it returns is the
    store's own characters, and those characters replace the model's quote.
    """
    if not quote or not text:
        return None
    start = text.find(quote)
    if start >= 0:
        return start, start + len(quote), "exact"
    folded_text, index = _folded(text)
    folded_quote = _folded(quote.strip())[0].strip()
    if len(folded_quote) < 4:
        return None
    at = folded_text.find(folded_quote)
    if at < 0:
        return None
    start, end = index[at], index[at + len(folded_quote) - 1] + 1
    return start, end, "normalised"


def numbers_in(quote):
    """Every number written in the quote: 300, 1,000, 5.5, 4 1/2, 4-1/2, 3/4, 4½."""
    found, rest = [], quote
    for whole, frac in re.findall(r"(\d+)?\s?([%s])" % "".join(FRACTIONS), rest):
        found.append(float(whole or 0) + FRACTIONS[frac])
    for m in MIXED.finditer(rest):
        if int(m.group(3)):
            found.append(int(m.group(1)) + int(m.group(2)) / int(m.group(3)))
    for m in FRACTION.finditer(rest):
        if int(m.group(2)):
            found.append(int(m.group(1)) / int(m.group(2)))
    for m in NUMBER.finditer(rest):
        found.append(float(m.group(1).replace(",", "")))
    return found


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _in(value, numbers):
    return any(abs(value - n) < 1e-6 for n in numbers)


def finish(proposal, product, extractor, assume_unit=None, target_unit=None):
    """A figure record from one proposal. Code sets start, end and span_found_in_text, and marks it unsure
    when the reported numbers are not in the quoted words or the unit cannot be compared."""
    text = product.get("text") or ""
    kind = proposal.get("kind") if proposal.get("kind") in ("single", "spread", "adjustable") else "single"
    value, low, high = proposal.get("value"), proposal.get("low"), proposal.get("high")
    if kind == "single" and not _is_number(value) and _is_number(low) and low == high:
        value = low
    if kind != "single" and _is_number(low) and _is_number(high):
        if low > high:
            low, high = high, low
        if low == high:
            kind, value = "single", low
    if kind == "single":
        low = high = value
    else:
        value = None
    unsure = bool(proposal.get("unsure"))
    reason = (proposal.get("unsure_reason") or "the reader marked it unsure") if unsure else None

    quote = proposal.get("quote") or ""
    found = locate(quote, text)
    record = {"store": product["store"], "product_id": product["product_id"], "figure": proposal.get("figure"),
              "kind": kind, "value": value, "low": low, "high": high, "unit": proposal.get("unit"),
              "quote": quote, "start": None, "end": None, "extractor": extractor, "span_found_in_text": False}
    if found:
        start, end, how = found
        record.update(quote=text[start:end], start=start, end=end, span_match=how,
                      span_found_in_text=rules.span_found({"start": start, "end": end, "quote": text[start:end]}, text))
        if how != "exact":
            record["quote_as_proposed"] = quote

    wanted = [value] if kind == "single" else [low, high]
    if not all(_is_number(v) for v in wanted):
        unsure, reason = True, reason or "no number was reported"
    elif found and not all(_in(v, numbers_in(record["quote"])) for v in wanted):
        unsure, reason = True, "the reported number is not in the quoted words"

    stated_unit = rules.unit_name(proposal.get("unit"))
    if stated_unit is None:
        if assume_unit:
            record.update(unit=assume_unit, unit_assumed=True)
        else:
            unsure, reason = True, reason or "the page gives the number without a unit"
    else:
        # the unit the sheet's limit is written in; without one, pounds for weights and inches for lengths
        base = rules.unit_name(target_unit) or ("lb" if stated_unit in ("lb", "kg") else
                                                 "in" if rules.FAMILY.get(stated_unit) == "length" else stated_unit)
        record["unit"] = base
        if stated_unit != base and rules.convert(1, stated_unit, base) is None:
            record["unit"] = stated_unit
            unsure, reason = True, reason or "stated in %s, which cannot be compared with %s" % (stated_unit, base)
        elif stated_unit != base and all(_is_number(v) for v in wanted):
            record.update(stated_unit=stated_unit, stated_value=value, stated_low=low, stated_high=high,
                          value=None if value is None else rules.convert(value, stated_unit, base),
                          low=rules.convert(low, stated_unit, base), high=rules.convert(high, stated_unit, base))
    if unsure:
        record.update(unsure=True, unsure_reason=reason)
    if record["span_found_in_text"]:
        apply_position_rule(record)
    return record


DIMS_HEADER = re.compile(r"\(?\b([hwdl])\s*x\s*([hwdl])(?:\s*x\s*([hwdl]))?\b\)?", re.I)
DIM_LABEL = re.compile(r"\d\s*(?:[\"”″]|in\.?|inch(?:es)?)?\s*\(?\s*(h|w|d|l|height|width|depth|length|high|wide|deep|long)\b",
                       re.I)
LETTER = {"height": "h", "high": "h", "width": "w", "wide": "w", "depth": "d", "deep": "d", "length": "l", "long": "l"}


def dimension_position(quote, numbers):
    """For a quote that lists several dimensions ("Product Dims (h x w x d): 1.63" x 31" x 14.75"", or
    "19.6" H x 30.3" W x 4.1" D"): which position the reported number sits in and what the store labels that
    position. None when the quote is not such a list. Code, so a reader that takes the depth for the width
    can be seen without a second model."""
    if not quote or " x " not in quote.lower().replace("×", "x"):
        return None
    text = quote.replace("×", "x")
    header = DIMS_HEADER.search(text)
    body = text[header.end():] if header else text
    parts = [p for p in re.split(r"\s+x\s+|(?<=[\"”″])\s*x\s*(?=\d)", body) if p.strip()]
    if len(parts) < 2:
        return None
    parts[0] = parts[0].rsplit(":", 1)[-1]  # words and a size name before the first dimension are not a dimension
    labels = [g.lower() for g in header.groups() if g] if header else []
    if not labels:  # a label after each number: 28.5"W x 17.5"D
        for part in parts:
            found = DIM_LABEL.findall(part)
            labels.append(LETTER.get(found[-1].lower(), found[-1].lower()) if found else None)
    wanted = [n for n in numbers if isinstance(n, (int, float))]
    holds = []
    for i, part in enumerate(parts):
        here = numbers_in(part)
        if wanted and all(any(abs(n - h) < 1e-6 for h in here) for n in wanted):
            holds.append((len(here) != len(wanted), i, part))  # a part that is exactly these numbers comes first
    if not holds:
        return {"position": None, "of": len(parts), "label": None, "labels": labels, "part": None}
    _, i, part = sorted(holds)[0]
    return {"position": i + 1, "of": len(parts), "label": labels[i] if i < len(labels) else None,
            "labels": labels, "part": part.strip()}


POSITION_REASON = "position in a dimension string does not match the label"


def expected_label(figure):
    """The dimension a figure name asks for: w for a width, h for a height, l for a length, d for a depth."""
    name = (figure or "").lower()
    for word, letter in (("width", "w"), ("height", "h"), ("length", "l"), ("depth", "d")):
        if word in name:
            return letter
    return None


def position_check(row):
    """For a figure quoted from a labelled list of dimensions: `{position, of, label, expected, ok}`; None for
    any other quote. `ok` is False when the store labels the position the number was taken from as a different
    dimension than the figure asks for (a depth reported as a width)."""
    stated = row.get("stated_unit")
    numbers = [row.get("stated_value")] if stated and row.get("kind") == "single" else \
        [row.get("stated_low"), row.get("stated_high")] if stated else \
        [row.get("value")] if row.get("kind") == "single" else [row.get("low"), row.get("high")]
    at = dimension_position(row.get("quote"), numbers)
    if not at:
        return None
    want = expected_label(row.get("figure"))
    return {"position": at["position"], "of": at["of"], "label": at["label"], "expected": want,
            "ok": None if at["label"] is None or want is None else at["label"] == want}


def apply_position_rule(row):
    """The rule, for every reader: a figure taken from the wrong labelled position is marked unsure, so it does
    not count. Returns True when this call marked it. A figure already unsure keeps its own reason."""
    at = position_check(row)
    if at is None:
        return False
    row["dimension"] = at
    if at["ok"] is False and not row.get("unsure"):
        row.update(unsure=True, unsure_reason=POSITION_REASON, caught_by="code: position in a dimension string")
        return True
    return False
