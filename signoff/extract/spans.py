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
        record["number_in_quote"] = False  # not a statement of the page: it is never put to a test

    stated_unit = rules.unit_name(proposal.get("unit"))
    if stated_unit is None:
        if assume_unit:
            record.update(unit=assume_unit, unit_assumed=True)
        else:
            record["unit"] = None  # stated with a label and no unit: shown, and "unclear: no unit stated" when compared
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
    label = proposal.get("label")
    if isinstance(label, str) and label.strip():
        record["label"] = label.strip()
    if record["span_found_in_text"]:
        apply_unambiguous_rule(record)
    return record



# --- one number, or a number the text itself labels ---------------------------------------------------------
# A figure counts only if its number is unambiguous in its quote. When the quote holds other numbers of the
# same kind of unit, the reader must name the label the text attaches to the number it chose, and code checks
# that pairing from the quote alone: by the order of a list of labels against the order of the values, or by
# the label standing next to the number. No format is named anywhere: any separated list and any label work
# the same way. If the text does not settle it, the figure is unsure.
AMBIGUOUS = "several numbers in the quote"
FAMILIES = (("length", r"(?:\"|”|″|''|inch(?:es)?\b|in\b\.?|cm\b|mm\b|ft\b|feet\b|foot\b)"),
            ("weight", r"(?:lbs?\b\.?|pounds?\b|kgs?\b|oz\b|ounces?\b)"),
            ("volume per flush", r"(?:gpf\b|g\.p\.f\.|lpf\b|gal(?:lons?)?\s*(?:per|/)\s*flush|l(?:iters?|itres?)?\s*(?:per|/)\s*flush)"),
            ("flow", r"(?:gpm\b|g\.p\.m\.|lpm\b|gal(?:lons?)?\s*(?:per|/)\s*min(?:ute)?|l(?:iters?|itres?)?\s*(?:per|/)\s*min(?:ute)?)"),
            ("volume", r"(?:qts?\b\.?|quarts?\b|liters?\b|litres?\b|l\b)"),
            ("temperature", r"(?:°\s?[fc]\b|degrees\b)"))
WRITTEN = re.compile(r"(?:(?<![\w./])(?:(?P<whole>\d+)[ -](?P<num>\d+)/(?P<den>\d+)(?![\w/])|(?P<fnum>\d+)/(?P<fden>\d+)(?![\w/])"
                     r"|(?P<plain>\d+(?:,\d{3})*(?:\.\d+)?|\.\d+)\s?(?P<uni>[%s])?)"
                     r"|(?<=\d/)(?P<slashed>\d+(?:\.\d+)?))" % "".join(FRACTIONS))  # 1.1/1.6 and 20/18/30: each its own number
NOT_UNITS = {"by", "to", "or", "and", "at", "of", "on", "per", "for", "the", "is", "are", "in", "x", "with", "from"}
JOIN = re.compile(r"^\s*(?:-|–|—|/|to\b|and\b|or\b)\s*$", re.I)
LIST_SEPARATORS = (r"\s+[x×]\s+", r"\s*/\s*", r"\s*,\s*", r"\s*\|\s*", r"\s+by\s+")


def family_of(unit):
    return rules.FAMILY.get(rules.unit_name(unit))


def quote_numbers(quote):
    """Every number written in the quote with where it is and the kind of unit written after it (or after the
    number it is joined to: "30 - 37\"" are both lengths)."""
    found, quote = [], quote or ""
    for m in WRITTEN.finditer(quote):  # "4 1/2" and "3/4" and "4½" are one number each, not three
        if quote[max(0, m.start() - 1):m.start()] == "#" or re.search(r"(?i)\bno\.\s*$", quote[:m.start()]):
            continue  # "#2" and "No. 2" name a grade or an item, they do not measure anything
        if m.group("whole") is not None:
            value = int(m.group("whole")) + int(m.group("num")) / max(int(m.group("den")), 1)
        elif m.group("fnum") is not None:
            value = int(m.group("fnum")) / max(int(m.group("fden")), 1)
        elif m.group("slashed") is not None:
            value = float(m.group("slashed"))
        else:
            value = float(m.group("plain").replace(",", "")) + FRACTIONS.get(m.group("uni") or "", 0)
        found.append({"value": value, "start": m.start(), "end": m.end(), "family": None})
    for n in found:
        tail = quote[n["end"]:n["end"] + 14].lstrip(" \t")
        if re.match(r"-[A-Za-z]", tail):
            tail = tail[1:]  # "10-inch" and "3-hole": the word joined to the number is its unit
        declared = [(rules.FAMILY.get(name, name), "(?:%s)(?![A-Za-z])" % "|".join(re.escape(x) for x in spellings))
                    for name, spellings in rules.DECLARED.items()]
        for name, pattern in declared + list(FAMILIES):
            if re.match(pattern, tail, re.I):
                n["family"] = name
                break
        else:  # a short unit-like word of some other kind ("60 PSI", "120 V") is a unit too, just not one of ours
            word = re.match(r"([A-Za-z]{2,4}|[a-z]{5,8})\b(?!\s*[:=])", tail)  # short, or a lower-case word: "hours"
            if word and word.group(1).lower() not in NOT_UNITS:
                n["family"] = "other unit"
    for i in range(len(found) - 2, -1, -1):  # a number joined to the next one shares its unit
        between = quote[found[i]["end"]:found[i + 1]["start"]]
        if found[i]["family"] is None and JOIN.match(re.sub(r"[\"”″]", "", between) or " "):
            found[i]["family"] = found[i + 1]["family"]
    return found


def chosen_numbers(row):
    """The numbers the reader reported, as they are written in the quote (before any unit conversion)."""
    if row.get("stated_unit"):
        return [row.get("stated_value")] if row.get("kind") == "single" else [row.get("stated_low"), row.get("stated_high")]
    return [row.get("value")] if row.get("kind") == "single" else [row.get("low"), row.get("high")]


def other_numbers(row):
    """Numbers in the quote that the reader did not choose and that could be the same kind of measure: the same
    kind of unit, or no unit written. A capacity in pounds beside a width in inches is not a rival."""
    chosen = [n for n in chosen_numbers(row) if isinstance(n, (int, float))]
    want = family_of(row.get("stated_unit") or row.get("unit"))
    return [n for n in quote_numbers(row.get("quote"))
            if not any(abs(n["value"] - c) < 1e-6 for c in chosen) and (n["family"] is None or n["family"] == want)]


def _find_label(quote, label):
    """Where the label stands in the quote: [(start, end)], whole words, any letter case."""
    words = [re.escape(w) for w in str(label).split()]
    if not words:
        return []
    return [(m.start(), m.end()) for m in re.finditer(r"(?<![A-Za-z0-9])" + r"\s+".join(words) + r"(?![A-Za-z0-9])", quote, re.I)]


def _by_order(quote, label, chosen):
    """The label is one of a separated list of labels, and the values are a list of the same length with the
    same separator: the label's place in its list says which value is meant. True, False, or None (no such lists)."""
    for sep in LIST_SEPARATORS:
        for m in re.finditer(r"(?<![A-Za-z0-9])[A-Za-z]{1,20}(?:%s[A-Za-z]{1,20}){1,7}(?![A-Za-z0-9])" % sep, quote):
            labels = [t.strip().lower() for t in re.split(sep, m.group(0))]
            if str(label).strip().lower() not in labels:
                continue
            place = labels.index(str(label).strip().lower())
            for region in (quote[m.end():], quote[:m.start()]):
                region = region.strip(" ():;=-–—")
                parts = [p for p in re.split(sep.replace(r"\s+", r"\s*"), region) if p.strip()]
                if len(parts) != len(labels) or not all(NUMBER.search(p) for p in parts):
                    continue
                here = [float(x.replace(",", "")) for x in NUMBER.findall(parts[place].rsplit(":", 1)[-1])]
                return all(any(abs(c - h) < 1e-6 for h in here) for c in chosen)
    return None


def _by_adjacency(quote, label, chosen):
    """The label stands next to a number: right after it (unit marks and a bracket may sit between), or before
    it with a colon or equals sign, or as the only number within a few words. True, False, or None (not settled)."""
    numbers = quote_numbers(quote)
    paired = []
    for start, end in _find_label(quote, label):
        before = [n for n in numbers if n["end"] <= start]
        after = [n for n in numbers if n["start"] >= end]
        gap_before = quote[before[-1]["end"]:start] if before else None
        gap_after = quote[end:after[0]["start"]] if after else None
        if gap_after is not None and re.fullmatch(r"\s*\)?\s*[:=]\s*", gap_after):
            paired.append(after[0]["value"])
        elif gap_before is not None and re.fullmatch(r"\s*(?:\"|”|″|''|[A-Za-z]{1,6}\.?)?\s*\(?\s*", gap_before):
            paired.append(before[-1]["value"])
        else:
            near = [v for gap, v in ((gap_before, before[-1]["value"] if before else None),
                                     (gap_after, after[0]["value"] if after else None))
                    if gap is not None and len(gap) <= 25 and not re.search(r"[.;!?]\s", gap)]
            if len(near) == 1:
                paired.append(near[0])
    if not paired:
        return None
    return all(any(abs(c - v) < 1e-6 for v in paired) for c in chosen) and \
        all(any(abs(c - v) < 1e-6 for c in chosen) for v in paired)


def pairing(quote, label, chosen):
    """Whether the text itself attaches `label` to the chosen number(s): (True | False | None, how)."""
    if not label or not _find_label(quote, label):
        return None, "the label is not in the quote"
    ordered = _by_order(quote, label, chosen)
    if ordered is not None:
        return ordered, "order of the labels against the order of the values"
    adjacent = _by_adjacency(quote, label, chosen)
    if adjacent is not None:
        return adjacent, "the label stands next to the number"
    return None, "the text does not settle which number the label belongs to"


def apply_unambiguous_rule(row):
    """The rule, for every reader. When the quote holds other candidate numbers and the text does not pair the
    reader's label with the number it chose, the page does not settle which number is the figure: the others
    are recorded in `possible` and every one of them is tested downstream (all pass: inside; all fail: outside;
    they differ: unclear). Returns True when this call found the number unsettled."""
    for key in ("number_check", "possible"):
        row.pop(key, None)
    if not row.get("span_found_in_text") or row.get("number_in_quote") is False:
        return False
    chosen = [n for n in chosen_numbers(row) if isinstance(n, (int, float))]
    others = other_numbers(row)
    if not chosen or not others:
        return False
    label = row.get("label")
    ok, how = pairing(row["quote"], label, chosen) if label else (None, "the reader gave no label for the number it chose")
    row["number_check"] = {"other_numbers": [("%g" % n["value"]) for n in others][:8], "label": label, "paired": ok, "how": how}
    if ok is True:
        return False
    scale = 1.0
    if row.get("stated_unit") and row.get("kind") == "single" and row.get("stated_value"):
        scale = (row.get("value") or 0) / row["stated_value"] if row["stated_value"] else 1.0  # same conversion as the chosen number
    row["possible"] = [round(n["value"] * scale, 2) for n in others][:8]
    return True


def _fold_label(text):
    """Option names as stores write them, made comparable: 12", 12” and 12 inch are the same option."""
    text = "".join(FOLD.get(ch, ch) for ch in str(text)).lower()
    text = re.sub(r"\s*(?:inch(?:es)?|in\.)(?![a-z])", '"', text)
    return re.sub(r"\s+", " ", text).strip()


def apply_option_rule(row, variant):
    """A product sold in several options: when the quote itself names an option that is not the one in the pool
    and does not name the one that is, the text ties the figure to another option, so it is unsure. Nothing is
    marked merely because a product has several options. Returns True when this call marked the figure."""
    row.pop("for_other_option", None)
    if not variant.get("other_option_labels"):
        return False
    quote = _fold_label(row.get("quote") or "")
    def named(label):
        label = _fold_label(label)
        return len(label) >= 2 and re.search(r"(?<![a-z0-9.])%s(?![a-z0-9])" % re.escape(label), quote) is not None
    others = [l for l in variant["other_option_labels"] if named(l)]
    if not others or any(named(l) for l in variant.get("option_labels") or []):
        return False
    row["for_other_option"] = "stated for the option %s, not for %s" % (", ".join(others[:3]), variant.get("variant_title"))
    return True


def ready(row, text):
    """A cached figure record made ready for the rules, the same way wherever it is loaded: the quote is looked
    up again in the text, marks left by the earlier, stricter handling are taken off (code's own, not the
    reader's), and the number rule records any other number the quote leaves possible."""
    row["span_found_in_text"] = rules.span_found(row, text)
    if str(row.get("caught_by") or "").startswith("code:") or row.get("unsure_reason") == "the page gives the number without a unit":
        for key in ("unsure", "unsure_reason", "caught_by"):
            row.pop(key, None)
    if row.get("unsure_reason") == "the reported number is not in the quoted words":
        row["number_in_quote"] = False
    if row.get("unsure"):
        row["reader_note"] = row.get("unsure_reason")
    if row["span_found_in_text"]:
        apply_unambiguous_rule(row)
    return row
