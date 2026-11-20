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
