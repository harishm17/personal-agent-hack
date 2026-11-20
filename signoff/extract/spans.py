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


def finish(proposal, product, extractor, assume_unit=None):
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
        base = "lb" if stated_unit in ("lb", "kg") else "in"
        record["unit"] = base
        if stated_unit != base and all(_is_number(v) for v in wanted):
            record.update(stated_unit=stated_unit, stated_value=value, stated_low=low, stated_high=high,
                          value=None if value is None else rules.convert(value, stated_unit, base),
                          low=rules.convert(low, stated_unit, base), high=rules.convert(high, stated_unit, base))
    if unsure:
        record.update(unsure=True, unsure_reason=reason)
    return record
