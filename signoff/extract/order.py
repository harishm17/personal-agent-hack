"""Derives the sheet's limits from the therapist's written order, so nobody configures them.

    uv run python -m signoff.extract.order          # reads the order once, writes data/order/derived.json

Same split as for store pages. The reading model proposes each limit: what is summed, the comparison, the
number and unit, and the order's own sentence. Code then
- finds that sentence in the order's text (inside the numbered item it belongs to, when the same words
  appear under several items) and sets `start`, `end`, `span_found_in_text`;
- checks the number is in the quoted sentence;
- matches each derived limit to a sheet limit by its line and by what it sums, and says whether comparison,
  value and unit are the same.
A limit whose bound is a measurement of the home ("must fit inside the tub") derives the rule and names the
measurement; the measurement's value comes from the home, not from the order.

The sheet file stays what the engine runs on. This output is shown beside it (`from_order` on each limit).
The read is batch work: `claude -p`, never the API key; read once and cached by the order's text.
"""
import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import sys

from signoff import config
from signoff.engine import paths, rules
from signoff.extract import reader, spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DOC = ROOT / "signoff" / "sign" / "senso_docs" / "order.txt"
OUT = ROOT / "data" / "order" / "derived.json"

SYSTEM = """You read a written equipment order and list the limits it sets, as data. You add nothing to it.

You are given the order's text and a vocabulary: the figures a store page can state, and the measurements
of the home that the shopper holds. For each numbered item of the order return its number, the words that
name the thing ordered, and every limit the order sets on it. A limit is:
- "terms": what is added up on the left side, each either {"source": "store", "figure": "<figure name>"}
  or {"source": "home", "measurement": "<measurement id>"}. Usually one term; two when the order adds a
  home measurement to a store figure.
- "op": ">=" when the order says at least, reach, hold, or that the product must take in something as
  large as a home measurement; "<=" when the order says at most, or that the product must fit inside or pass
  through something; "==" when the order says the product must match or equal something.
- "bound": {"kind": "number", "value": <number>, "unit": "<unit as written>"} when the order gives a
  number, or {"kind": "home", "measurement": "<measurement id>"} when the order compares with a
  measurement of the home and gives no number.
- "quote": the one sentence of the order that sets this limit, copied character for character. When the
  order says the same thing twice, quote the sentence under the numbered item.
If the order says how an item must be obtained (for example picked up locally and not bought through a
cart), return that as "fulfilment": {"how": "pick_up_locally", "quote": "<the sentence>"} on the item.
Use only names from the vocabulary. If a requirement cannot be expressed with it, return it with
"terms": [] and "unmapped": true. Do not invent a limit, a number or a unit that the order does not state.

Answer with one JSON object and nothing else:
{"title": "<the order's own first words that name it>", "issuer": "<who ordered, as written>",
 "items": [{"item": 1, "need": "...", "limits": [{"terms": [...], "op": ">=", "bound": {...}, "quote": "..."}],
            "fulfilment": null}]}"""


def doc_of(sheet):
    """The order document of a sheet, as a path from the repository root: the sheet's `order_doc`, or sheet 1's."""
    return sheet.get("order_doc") or str(DOC.relative_to(ROOT))


def out_of(sheet_id):
    return paths.of(sheet_id)["order"]


def vocabulary(sheet):
    figures = sorted({t["figure"] for line in sheet["lines"] for l in line["limits"] for t in l["terms"]
                      if t["source"] == "store"})
    meanings = sheet.get("figures") or {}  # the sheet's own words; a figure without them is given by name
    return ("Figures a store page can state:\n%s\n\nMeasurements of the home (the shopper holds the values; you "
            "only need the names):\n%s" % (
                "\n".join("- %s: %s" % (n, meanings.get(n, n.replace("_", " "))) for n in figures),
                "\n".join("- %s: %s" % (f["id"], f["label"]) for f in sheet["shopper_facts"])))


def item_spans(text):
    """{item number: (start, end)} of each numbered item's own lines, so a repeated sentence is found in its item."""
    marks = [(int(m.group(1)), m.start()) for m in re.finditer(r"(?m)^(\d+)\.\s", text)]
    out = {}
    for i, (n, start) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else text.find("\n\n", start)
        out[n] = (start, len(text) if end < 0 else end)
    return out


def locate(quote, text, item_span=None):
    if item_span:
        found = spans.locate(quote, text[item_span[0]:item_span[1]])
        if found:
            return found[0] + item_span[0], found[1] + item_span[0], found[2]
    return spans.locate(quote, text)


def line_for(need, sheet):
    need = (need or "").lower()
    for line in sheet["lines"]:
        if line["need"].lower() in need or need in line["need"].lower():
            return line
    return None


def as_sheet_terms(terms):
    out = []
    for t in terms or []:
        if t.get("source") == "store" and t.get("figure"):
            out.append({"source": "store", "figure": t["figure"]})
        elif t.get("source") == "home" and t.get("measurement"):
            out.append({"source": "shopper", "fact": t["measurement"]})
    return out


def term_key(terms):
    return sorted((t["source"], t.get("figure") or t.get("fact")) for t in terms)


def same_as_sheet(derived, limit):
    """Whether a derived limit and a sheet limit say the same thing: comparison, value or measurement, unit."""
    b = limit["bound"]
    if derived["op"] != limit["op"] or derived["unit"] != limit["unit"]:
        return False
    if derived["bound"]["source"] == "issuer":
        return b["source"] == "issuer" and abs(float(b["value"]) - float(derived["value"])) < 1e-9
    return b["source"] == "shopper" and b["fact"] == derived["bound"]["fact"]


def derive(text, sheet, model=None):
    """The order read once: (document dict for derived.json)."""
    model = model or config.env("SIGNOFF_READER_MODEL") or reader.DEFAULT_MODEL
    rules.declare_units(sheet)
    user = "%s\n\nThe order, between the markers:\n<<<ORDER\n%s\nORDER>>>" % (vocabulary(sheet), text)
    reply, usage, extractor = reader.ask(model, SYSTEM, user, purpose="read the limits from the written order",
                                         fact_classes=["order", "limit", "person"])
    obj = json.loads(reply[reply.find("{"):reply.rfind("}") + 1])
    facts = {f["id"]: f for f in sheet["shopper_facts"]}
    in_item, limits, fulfilment, unmapped = item_spans(text), [], [], []
    for item in obj.get("items") or []:
        line = line_for(item.get("need"), sheet)
        span = in_item.get(item.get("item"))
        how = item.get("fulfilment")
        if isinstance(how, dict) and how.get("quote"):
            found = locate(how["quote"], text, span)
            fulfilment.append({"line_id": line and line["id"], "how": how.get("how"),
                               "quote": text[found[0]:found[1]] if found else how["quote"],
                               "start": found[0] if found else None, "end": found[1] if found else None,
                               "span_found_in_text": bool(found),
                               "matches": bool(line) and line.get("fulfilment") == how.get("how")})
        for proposed in item.get("limits") or []:
            terms, bound = as_sheet_terms(proposed.get("terms")), proposed.get("bound") or {}
            found = locate(str(proposed.get("quote") or ""), text, span)
            quote = text[found[0]:found[1]] if found else str(proposed.get("quote") or "")
            row = {"limit_id": None, "line_id": line and line["id"], "item": item.get("item"), "need": item.get("need"),
                   "terms": terms, "op": proposed.get("op"), "value": None, "unit": None, "bound": None,
                   "quote": quote, "start": found[0] if found else None, "end": found[1] if found else None,
                   "extractor": extractor, "span_found_in_text": bool(found)}
            if bound.get("kind") == "number" and isinstance(bound.get("value"), (int, float)):
                unit = rules.unit_name(bound.get("unit"))
                row.update(value=bound["value"], unit=unit, bound={"source": "issuer", "value": bound["value"]},
                           value_in_quote=any(abs(bound["value"] - n) < 1e-9 for n in spans.numbers_in(quote)))
            elif bound.get("kind") == "home" and bound.get("measurement") in facts:
                fact = facts[bound["measurement"]]  # the rule comes from the order; the value comes from the home
                row.update(unit=fact["unit"], bound={"source": "shopper", "fact": fact["id"]},
                           measurement={"id": fact["id"], "label": fact["label"], "source": "from the home"})
            usable = terms and row["bound"] and row["op"] in rules.OPS and row["span_found_in_text"] and \
                row.get("value_in_quote", True) and not proposed.get("unmapped")
            match = None
            if usable and line:
                same_terms = [l for l in line["limits"] if term_key(l["terms"]) == term_key(terms)]
                # two limits on the same measure (an upper and a lower one) are told apart by their comparison
                match = next((l for l in same_terms if l["op"] == row["op"]), same_terms[0] if len(same_terms) == 1 else None)
            if match:
                row.update(limit_id=match["id"], name=match["name"], equals_sheet=same_as_sheet(row, match))
            if not usable or not match:
                unmapped.append(row)
            else:
                limits.append(row)
    in_sheet = [l["id"] for line in sheet["lines"] for l in line["limits"]]
    derived_ids = [r["limit_id"] for r in limits]
    return {"doc": doc_of(sheet), "doc_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "title": obj.get("title"), "issuer": obj.get("issuer"), "sheet_id": sheet["id"],
            "derived_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "extractor": extractor,
            "limits": limits, "fulfilment": fulfilment, "not_usable": unmapped,
            "sheet_limits_not_in_the_order": [i for i in in_sheet if i not in derived_ids],
            "limits_derived": len(limits), "limits_equal_to_the_sheet": sum(1 for r in limits if r["equals_sheet"]),
            "usage": usage}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--doc", default=None, help="default: the sheet's order_doc")
    ap.add_argument("--sheet", default=os.environ.get("SIGNOFF_SHEET") or "sheet1")
    ap.add_argument("--out", default=None, help="default: data/order/derived.json, or data/figures/<sheet>/_order/")
    ap.add_argument("--force", action="store_true", help="read the order again even if its text has not changed")
    args = ap.parse_args(argv)
    sheet = json.loads((ROOT / "sheets" / (args.sheet + ".json")).read_text())
    text = pathlib.Path(args.doc or ROOT / doc_of(sheet)).read_text()
    out = pathlib.Path(args.out or out_of(args.sheet))
    if out.exists() and not args.force:
        held = json.loads(out.read_text())
        if held.get("doc_sha256") == hashlib.sha256(text.encode()).hexdigest():
            print("the order has not changed since %s: keeping the cached reading (%d limits)" % (
                held["derived_at"], held["limits_derived"]))
            return 0
    made = derive(text, sheet)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(made, indent=1, ensure_ascii=False) + "\n")
    print("%d limits derived from %s, %d equal to the sheet; not usable: %d; in the sheet but not in the order: %s" % (
        made["limits_derived"], made["doc"], made["limits_equal_to_the_sheet"], len(made["not_usable"]),
        made["sheet_limits_not_in_the_order"]))
    for r in made["limits"]:
        print("  %-13s %-28s %s %-22s %s | %r" % (
            r["limit_id"], " + ".join(t.get("figure") or t.get("fact") for t in r["terms"]), r["op"],
            ("%g %s" % (r["value"], r["unit"])) if r["value"] is not None else r["bound"]["fact"],
            "= sheet" if r["equals_sheet"] else "DIFFERS", r["quote"][:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
