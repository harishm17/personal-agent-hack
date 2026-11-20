"""One figure record per (product, figure) from several readers' records. Code decides, by policy:

    first  the first reader (the reference) decides; each record lists the other readers that give the
           same kind and numbers (`agreed_by`) so agreement can be shown and measured.
    agree  a figure counts only when every deciding reader gives the same kind and the same numbers,
           each with a quote found in the store's text.

Anything that does not count is kept and shown, marked unsure with the reason, and the engine treats it as
not stated. Readers listed as evidence (the small entity model) never decide; when they mark the same place
with the same number, the record says so.
"""


def counted(row):
    return bool(row) and row.get("span_found_in_text") and not row.get("unsure")


def numbers(row):
    return (row["kind"], row["value"]) if row["kind"] == "single" else (row["kind"], row["low"], row["high"])


def same(a, b):
    na, nb = numbers(a), numbers(b)
    if any(not isinstance(v, (int, float)) for v in na[1:] + nb[1:]):
        return False  # a record without its number agrees with nothing
    return len(na) == len(nb) and na[0] == nb[0] and all(abs(x - y) <= 0.01 for x, y in zip(na[1:], nb[1:]))


def shown(row):
    return "%g" % row["value"] if row["kind"] == "single" else "%g to %g (%s)" % (row["low"], row["high"], row["kind"])


def brief(row):
    return {k: row.get(k) for k in ("extractor", "kind", "value", "low", "high", "unit", "quote", "start", "end",
                                    "span_found_in_text", "unsure_reason") if row.get(k) is not None}


def overlaps(a, b):
    return None not in (a.get("start"), a.get("end"), b.get("start"), b.get("end")) and \
        a["start"] < b["end"] and b["start"] < a["end"]


def numbers_at(rows):
    """{(store, product, variant, figure): the numbers a reader states there}."""
    out = {}
    for r in rows:
        if r.get("span_found_in_text") and r.get("number_in_quote") is not False:
            numbers = [r.get("value")] if r.get("kind") == "single" else [r.get("low"), r.get("high")]
            out.setdefault((r["store"], r["product_id"], r.get("variant_id"), r["figure"]), set()).update(
                n for n in numbers if isinstance(n, (int, float)))
    return out


def combine(deciding, evidence=(), policy="first"):
    """The records the engine uses: every statement of the first reader (the reference), each one noting
    which other readers state the same numbers for that figure on that page (`agreed_by`). The other readers'
    own records stay in their run folders and are compared after the rules by `signoff.extract.score`.
    `deciding` and `evidence` are lists of (reader name, rows)."""
    if not deciding:
        return []
    others = [(name, numbers_at(rows)) for name, rows in list(deciding[1:]) + list(evidence)]
    out = []
    for row in deciding[0][1]:
        row = dict(row)
        key = (row["store"], row["product_id"], row.get("variant_id"), row["figure"])
        mine = {n for n in ([row.get("value")] if row.get("kind") == "single" else [row.get("low"), row.get("high")])
                if isinstance(n, (int, float))}
        if row.get("span_found_in_text") and mine:
            row["agreed_by"] = [deciding[0][0]] + [name for name, at in others if mine <= at.get(key, set())]
        out.append(row)
    return out
