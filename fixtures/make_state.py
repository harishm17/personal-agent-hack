"""Builds fixtures/pool.json, fixtures/figures.json, fixtures/store_answers.json and fixtures/state.json.

Placeholder products only (no real brand, no real store text). This file is also the reference for the
check and pick rules in CONTRACT.md "Rules code decides"; the ENGINE stream reimplements them in
signoff/engine and must reproduce fixtures/state.json from the three input fixtures.

Run: uv run python fixtures/make_state.py
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHEET = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
NOW = "2026-11-20T11:05:00-08:00"
STORES = ["fixture-store-a.example", "fixture-store-b.example", "fixture-store-c.example"]

# line, store index, letter, price cents, sentences. A sentence is (figure, kind, low, high, unit, text) or text.
RAW = [
    ("L2", 0, "A", 2752, [("weight_capacity", "single", 300, 300, "lb", "Holds up to 300 lb."),
                          ("added_height", "spread", 5.0, 5.5, "in", "Adds 5 to 5.5 inches of height to the toilet seat.")]),
    ("L2", 1, "B", 5800, [("weight_capacity", "single", 400, 400, "lb", "Supports 400 lb."),
                          ("added_height", "single", 4.5, 4.5, "in", "Raises the seat by 4.5 inches.")]),
    ("L2", 1, "C", 6499, [("weight_capacity", "single", 500, 500, "lb", "Rated for 500 lb."),
                          ("added_height", "single", 5.0, 5.0, "in", "Adds 5 inches.")]),
    ("L2", 2, "D", 7999, [("weight_capacity", "single", 450, 450, "lb", "Weight capacity 450 lb."),
                          ("added_height", "single", 5.0, 5.0, "in", "Adds 5 inches of height.")]),
    ("L2", 2, "E", 8999, [("weight_capacity", "single", 400, 400, "lb", "Holds 400 lb."),
                          ("added_height", "single", 4.0, 4.0, "in", "Adds 4 inches.")]),
    ("L2", 0, "F", 4900, [("weight_capacity", "single", 250, 250, "lb", "Holds up to 250 lb."),
                          ("added_height", "single", 5.0, 5.0, "in", "Adds 5 inches.")]),
    ("L2", 0, "G", 2400, [("weight_capacity", "single", 325, 325, "lb", "Supports 325 lb."),
                          ("added_height", "single", 3.5, 3.5, "in", "Raises the seat 3.5 inches.")]),
    ("L2", 1, "H", 3999, [("added_height", "single", 4.0, 4.0, "in", "Adds 4 inches."), "Sturdy and easy to clean."]),
    ("L2", 2, "I", 2200, [("weight_capacity", "single", 300, 300, "lb", "Holds 300 lb."), "Fits most standard toilets."]),
    ("L1", 0, "J", 7538, [("weight_capacity", "single", 500, 500, "lb", "Holds up to 500 lb."),
                          ("overall_width", "single", 20.0, 20.0, "in", "Overall width 20 inches.")]),
    ("L1", 1, "K", 5499, [("weight_capacity", "single", 300, 300, "lb", "Supports 300 lb."),
                          ("overall_width", "single", 23.0, 23.0, "in", "Overall width 23 inches.")]),
    ("L1", 2, "L", 4899, [("weight_capacity", "single", 350, 350, "lb", "Rated for 350 lb."), "Seat width 16 inches."]),
    ("L3", 0, "M", 8899, [("weight_capacity", "single", 350, 350, "lb", "Holds 350 lb."),
                          ("seat_height", "adjustable", 16.0, 21.0, "in", "Seat height adjusts from 16 to 21 inches.")]),
    ("L3", 2, "N", 9450, [("weight_capacity", "single", 300, 300, "lb", "Holds 300 lb."),
                          ("seat_height", "adjustable", 17.0, 23.0, "in", "Seat height adjusts from 17 to 23 inches.")]),
    ("L4", 0, "O", 6999, [("weight_capacity", "single", 350, 350, "lb", "Supports 350 lb."),
                          ("overall_width", "single", 27.5, 27.5, "in", "Overall width 27.5 inches.")]),
    ("L4", 2, "P", 5999, [("weight_capacity", "single", 300, 300, "lb", "Supports 300 lb."),
                          ("overall_width", "single", 29.0, 29.0, "in", "Overall width 29 inches.")]),
    ("L5", 1, "Q", 1899, [("weight_capacity", "single", 500, 500, "lb", "Supports 500 lb when screw-mounted."),
                          ("length", "single", 18.0, 18.0, "in", "Length 18 inches.")]),
    ("L6", 0, "R", 6499, [("weight_capacity", "single", 300, 300, "lb", "Holds 300 lb."), "Fits most beds."]),
    ("L6", 2, "S", 7299, [("mattress_thickness_max", "single", 14.0, 14.0, "in", "Fits mattresses up to 14 inches thick."),
                          "Tool-free assembly."]),
]
ANSWERS = [
    {"store": STORES[0], "asked_at": NOW, "question": "How long does delivery take, and can an opened item be returned?",
     "answer": "Fixture reply: standard shipping takes 3 to 5 days. Bath seats cannot be returned.",
     "delivery": {"stated": True, "quote": "standard shipping takes 3 to 5 days", "days_low": 3, "days_high": 5},
     "returns": {"returnable": "no", "fee": None, "quote": "Bath seats cannot be returned", "applies_to": "bath seats"}},
    {"store": STORES[1], "asked_at": NOW, "question": "How long does delivery take, and can an opened item be returned?",
     "answer": "Fixture reply: we do not have delivery times. Returns within 30 days if unused.",
     "delivery": {"stated": False, "quote": None, "days_low": None, "days_high": None},
     "returns": {"returnable": "unclear", "fee": None, "quote": "Returns within 30 days if unused", "applies_to": "all"}},
    {"store": STORES[2], "asked_at": NOW, "question": "How long does delivery take, and can an opened item be returned?",
     "answer": "Fixture reply: ground shipping takes 1 to 5 business days, not guaranteed. Returns within 30 days.",
     "delivery": {"stated": True, "quote": "ground shipping takes 1 to 5 business days", "days_low": 1, "days_high": 5},
     "returns": {"returnable": "yes", "fee": "restocking fee may apply", "quote": "Returns within 30 days", "applies_to": "all"}},
]
STRIKES = [{"line_id": "L3", "product_key": "fixture m", "by": "issuer",
            "reason": "He cannot use a frame with fixed arms (fixture reason)", "at": NOW}]


def build_inputs():
    pool, figures = [], []
    for line_id, si, letter, price, parts in RAW:
        text, spans = "Fixture product %s. " % letter, []
        for part in parts:
            sentence = part if isinstance(part, str) else part[5]
            if not isinstance(part, str):
                spans.append((part, len(text), len(text) + len(sentence)))
            text += sentence + " "
        pid = "fx-" + letter
        pool.append({"store": STORES[si], "product_id": pid, "variant_id": pid + "-v1",
                     "title": "Fixture product " + letter, "price_cents": price,
                     "url": "https://%s/products/%s" % (STORES[si], pid), "text": text.strip(),
                     "fetched_at": NOW, "product_key": "fixture " + letter.lower(), "line_ids": [line_id]})
        for (fig, kind, low, high, unit, sentence), start, end in spans:
            figures.append({"store": STORES[si], "product_id": pid, "figure": fig, "kind": kind,
                            "value": low if kind == "single" else None, "low": low, "high": high, "unit": unit,
                            "quote": sentence, "start": start, "end": end, "extractor": "fixture",
                            "span_found_in_text": text[start:end] == sentence})
    return pool, figures


def deciding(fig, op):
    """A spread uses the end that could fail. An adjustable range uses the end that reaches furthest."""
    if fig["kind"] == "single":
        return fig["value"]
    if fig["kind"] == "spread":
        return fig["low"] if op == ">=" else fig["high"]
    return fig["high"] if op == ">=" else fig["low"]


def check(limit, product, figs, facts, sheet):
    terms, lhs, missing, adjustable = [], 0.0, None, None
    for t in limit["terms"]:
        if t["source"] == "shopper":
            f = facts[t["fact"]]
            terms.append({"owner": "shopper", "owner_name": sheet["shopper"]["name"], "label": f["short"],
                          "fact": f["id"], "value": f["value"], "unit": f["unit"]})
            lhs += f["value"]
        else:
            fig = figs.get((product["store"], product["product_id"], t["figure"]))
            if not fig or not fig["span_found_in_text"]:
                missing = t["figure"]
                terms.append({"owner": "store", "owner_name": product["store"], "label": t["figure"].replace("_", " "),
                              "figure": t["figure"], "value": None, "unit": limit["unit"]})
                continue
            v = deciding(fig, limit["op"])
            if fig["kind"] == "adjustable":
                adjustable = fig
            terms.append({"owner": "store", "owner_name": product["store"], "label": t["figure"].replace("_", " "),
                          "figure": t["figure"], "value": v, "unit": fig["unit"], "kind": fig["kind"],
                          "low": fig["low"], "high": fig["high"], "quote": fig["quote"],
                          "start": fig["start"], "end": fig["end"]})
            lhs += v
    b = limit["bound"]
    if b["source"] == "issuer":
        bound = {"owner": "issuer", "owner_name": sheet["issuer"]["name"], "value": b["value"], "unit": limit["unit"]}
    else:
        f = facts[b["fact"]]
        bound = {"owner": "shopper", "owner_name": sheet["shopper"]["name"], "fact": f["id"], "label": f["short"],
                 "value": f["value"], "unit": f["unit"]}
    out = {"limit_id": limit["id"], "name": limit["name"], "terms": terms, "op": limit["op"], "bound": bound}
    if missing:
        out.update({"lhs": None, "expr": None, "pass": False, "margin": None, "state": "not_stated",
                    "missing_figure": missing})
        return out
    ok = lhs >= bound["value"] if limit["op"] == ">=" else lhs <= bound["value"]
    if adjustable and ok:  # an adjustable range passes only when the limit lies inside it
        others = lhs - deciding(adjustable, limit["op"])
        ok = adjustable["low"] + others <= bound["value"] <= adjustable["high"] + others
    margin = round(lhs - bound["value"] if limit["op"] == ">=" else bound["value"] - lhs, 2)
    shown = " + ".join("%g" % t["value"] for t in terms)
    expr = ("%s = %g %s %g" % (shown, lhs, limit["op"], bound["value"])) if len(terms) > 1 else \
        "%g %s %g" % (lhs, limit["op"], bound["value"])
    out.update({"lhs": round(lhs, 2), "expr": expr, "pass": ok, "margin": margin, "state": "pass" if ok else "fail"})
    return out


def build_state(sheet, pool, figures, answers, strikes, mode="fixture"):
    facts = {f["id"]: f for f in sheet["shopper_facts"]}
    figs = {(f["store"], f["product_id"], f["figure"]): f for f in figures}
    ans = {a["store"]: a for a in answers}
    lines, found, every, inside_n, ready = [], len(pool), 0, 0, 0
    for line in sheet["lines"]:
        struck = [s for s in strikes if s["line_id"] == line["id"]]
        struck_keys = {s["product_key"] for s in struck}
        cands = []
        for p in pool:
            if line["id"] not in p["line_ids"]:
                continue
            checks = [check(l, p, figs, facts, sheet) for l in line["limits"]]
            a = ans.get(p["store"], {})
            d = a.get("delivery") or {"stated": False}
            missing = [c["missing_figure"] for c in checks if c["state"] == "not_stated"]
            if p["product_key"] in struck_keys:
                status, reason = "struck", next(s["reason"] for s in struck if s["product_key"] == p["product_key"])
            elif missing:
                status, reason = "not_stated", "%s never stated on the page" % missing[0].replace("_", " ")
            elif all(c["pass"] for c in checks):
                status, reason = "inside", None
            else:
                bad = next(c for c in checks if not c["pass"])
                status, reason = "outside", "%s: %s is false" % (bad["name"], bad["expr"])
            every += 0 if missing else 1
            cands.append({
                "id": "%s:%s:%s" % (line["id"], p["store"], p["product_id"]),
                "order_line": {"id": line["id"], "need": line["need"], "room": line["room"]},
                "product": {k: p[k] for k in ("store", "product_id", "variant_id", "title", "price_cents", "url",
                                              "fetched_at", "product_key")},
                "figures": [f for f in figures if f["store"] == p["store"] and f["product_id"] == p["product_id"]],
                "checks": checks,
                "arrival": {"need_by": sheet["need_by"], "status": "stated" if d.get("stated") else "not stated",
                            "quote": d.get("quote"), "days_low": d.get("days_low"), "days_high": d.get("days_high")},
                "undo": a.get("returns"), "senso": None, "status": status, "reason": reason,
                "strike": next((s for s in struck if s["product_key"] == p["product_key"]), None),
                "action": None, "picked": False})
        inside = [c for c in cands if c["status"] == "inside"]
        local = line["fulfilment"] == "pick_up_locally"  # nothing is shipped, so no delivery time is needed
        eligible = sorted((c for c in inside if local or c["arrival"]["status"] == "stated"),
                          key=lambda c: (c["product"]["price_cents"], c["id"]))
        pick = eligible[0] if eligible else None
        inside_n += len(inside)
        if pick:
            pick["picked"] = True
            status = "pick_up" if line["fulfilment"] == "pick_up_locally" else ("next_candidate" if struck else "ready")
            reason = line.get("fulfilment_note") if status == "pick_up" else None
            ready += 1 if status in ("ready", "next_candidate") else 0
            passed = sorted((c for c in pick["checks"]), key=lambda c: c["margin"])
            t = passed[0]
            tightest = {"limit_id": t["limit_id"], "name": t["name"], "margin": t["margin"], "unit": t["bound"]["unit"],
                        "text": "nothing to spare" if t["margin"] == 0 else "%g %s to spare" % (t["margin"], t["bound"]["unit"])}
        else:
            status, tightest = "open", None
            reason = "no page states every figure" if not inside and any(c["status"] == "not_stated" for c in cands) \
                else ("nothing inside the limits" if not inside else "nothing inside the limits states a delivery time")
        lines.append({"line_id": line["id"], "need": line["need"], "room": line["room"], "status": status,
                      "reason": reason, "pick": pick["id"] if pick else None, "tightest": tightest,
                      "why": {"total": len(cands), "inside": len(inside), "with_delivery_time": len(eligible),
                              "rule": sheet["pick_rule"]["label"],
                              "pick_price_cents": pick["product"]["price_cents"] if pick else None},
                      "struck": struck, "candidates": cands})
    total = sum(c["product"]["price_cents"] for l in lines for c in l["candidates"]
                if c["picked"] and l["status"] in ("ready", "next_candidate"))
    return {"version": 1, "mode": mode, "sheet": sheet,
            "seal": {"signed": False, "text": "Not signed. No cart exists at any store.", "sheet_hash": None,
                     "signature": None, "carts": []},
            "issuer_key": {"enrolled": False, "key_id": None, "persona": None},
            "counts": {"products_found": found, "state_every_figure": every, "inside_limits": inside_n,
                       "lines_ready": ready, "lines_total": len(lines), "hand_checked": False},
            "total_cents": total, "store_answers": answers, "lines": lines}


if __name__ == "__main__":
    pool, figures = build_inputs()
    out = ROOT / "fixtures"
    (out / "pool.json").write_text(json.dumps(pool, indent=1) + "\n")
    (out / "figures.json").write_text(json.dumps(figures, indent=1) + "\n")
    (out / "store_answers.json").write_text(json.dumps(ANSWERS, indent=1) + "\n")
    (out / "strikes.json").write_text(json.dumps(STRIKES, indent=1) + "\n")
    state = build_state(SHEET, pool, figures, ANSWERS, STRIKES)
    (out / "state.json").write_text(json.dumps(state, indent=1) + "\n")
    for l in state["lines"]:
        print(l["line_id"], l["need"], "|", l["status"], "|", l["reason"] or "", "|", l["pick"], "|", l["tightest"] and l["tightest"]["text"], "|", l["why"])
    print(state["counts"], "total", state["total_cents"])
