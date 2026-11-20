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


def combine(deciding, evidence=(), policy="first"):
    """`deciding` and `evidence` are lists of (extractor name, rows). The first deciding reader is the one
    whose quote is shown. Policy `first` lets the first reader decide alone (the others are still recorded)."""
    keys, by_reader = [], []
    for name, rows in list(deciding) + list(evidence):
        index = {}
        for r in rows:
            key = (r["store"], r["product_id"], r["figure"])
            index.setdefault(key, r)
            if key not in keys:
                keys.append(key)
        by_reader.append((name, index))
    out = []
    for key in keys:
        have = [(name, index[key]) for name, index in by_reader[:len(deciding)] if key in index]
        if not have:
            continue  # only the evidence reader marked something: recorded in its own run, not a figure
        good = [(n, r) for n, r in have if counted(r)]
        base = dict((good or have)[0][1])
        base["readers"] = [brief(r) for _, r in have]
        agreed = len(good) == len(deciding) and all(same(good[0][1], r) for _, r in good[1:])
        if policy == "first":
            if have[0][0] != deciding[0][0]:
                continue  # the reference reader reports nothing here: other readers' records stay in their runs
            base = dict(have[0][1], readers=base["readers"])
            if counted(base):
                base["agreed_by"] = [n for n, r in good if same(base, r)]
        elif agreed:
            base.pop("unsure", None), base.pop("unsure_reason", None)
            base["agreed_by"] = [n for n, _ in good]
        else:
            if len(good) >= 2 and not all(same(good[0][1], r) for _, r in good[1:]):
                reason = "readers differ: " + "; ".join("%s reads %s" % (n, shown(r)) for n, r in good)
            elif any(r.get("unsure") for _, r in have):
                n, r = next((n, r) for n, r in have if r.get("unsure"))
                reason = "%s is unsure: %s" % (n, r.get("unsure_reason"))
            elif any(not r.get("span_found_in_text") for _, r in have):
                reason = "a reader's quote is not in the store's text"
            else:
                reason = "only %s reports it; %s does not" % (
                    ", ".join(n for n, _ in have), ", ".join(n for n, _ in deciding if n not in [h[0] for h in have]))
            base.update(unsure=True, unsure_reason=reason)
        for name, index in by_reader[len(deciding):]:
            mark = index.get(key)
            if mark and counted(mark) and counted(base) and overlaps(mark, base) and mark["kind"] == base["kind"] and same(mark, base):
                base.setdefault("also_marked_by", []).append(
                    {"extractor": name, "start": mark["start"], "end": mark["end"], "quote": mark["quote"]})
        out.append(base)
    return out
