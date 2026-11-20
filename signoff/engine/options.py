"""Every option on sale is its own candidate (rule 2).

The STORE stream's pool has one row per product with `options`: `[{variant_id, title, price_cents, available}]`.
`expand` turns a row into one row per in-stock option: its own variant id and price, and the option's name as
the last line of its text ("Selected option: 18 Inch."), which is how the page looks with that option chosen.
A product with one option, or none listed, stays one row with its text as the store gave it.
"""
import re

SELECTED = re.compile(r"\n?Selected option:[^\n]*$")
NO_NAME = {"default title", "each", ""}


def page_text(row):
    """The product's text without any option line: the page as every option shares it."""
    return SELECTED.sub("", row.get("text") or "")


def expand(rows):
    out = []
    for row in rows:
        options = [o for o in row.get("options") or [] if o.get("available", True) and o.get("variant_id")]
        if len(options) <= 1:
            out.append(dict(row, options_on_sale=max(len(options), 1)))
            continue
        base = page_text(row)
        for option in options:
            title = str(option.get("title") or "").strip()
            named = title.lower() not in NO_NAME
            out.append(dict(row, variant_id=option["variant_id"], price_cents=option.get("price_cents", row.get("price_cents")),
                            variant_title=title or row.get("variant_title"),
                            text=base + ("\nSelected option: %s." % title if named else ""),
                            options_on_sale=len(options)))
    return out


def named_figures(row, sheet, quote_numbers, unit_name, family_of):
    """What an option's own name states: `[{figure, value, unit, quote, start, end}]`.

    An option is named by the store ("18 Inch", "12\" / Polished", "24 Pack"). A number in that name with a unit
    states a figure when exactly one figure asked of the candidate's lines is measured in that kind of unit;
    with none or several, the name is not read as a figure. The quote is the option's name as it stands in the
    candidate's own text (its last line), so it has a span like any other statement."""
    title = str(row.get("variant_title") or "")
    text = row.get("text") or ""
    if row.get("options_on_sale", 1) <= 1 or not title or not text.rstrip(".").endswith(title):
        return []
    at = text.rstrip(".").rfind(title)
    asked = {}
    for line in sheet["lines"]:
        if line["id"] in (row.get("line_ids") or []):
            for limit in line["limits"]:
                for term in limit["terms"]:
                    if term["source"] == "store":
                        asked.setdefault(family_of(limit["unit"]), {})[term["figure"]] = limit["unit"]
    out = []
    for n in quote_numbers(title):
        figures = asked.get(n["family"]) if n["family"] not in (None, "other unit") else None
        if not figures or len(figures) != 1:
            continue
        figure, unit = next(iter(figures.items()))
        written = title[n["end"]:].lstrip(" -")
        stated_unit = unit_name(written.split()[0].strip(".,/")) if written.split() else None
        if stated_unit is None:
            stated_unit = unit_name(written[:1])  # a mark such as "
        if stated_unit != unit_name(unit):
            continue  # stated in another unit of the same kind: left to the page's own statements
        out.append({"figure": figure, "value": n["value"], "unit": unit_name(unit), "quote": title,
                    "start": at, "end": at + len(title)})
    return out
