"""Everything the shopper's agent can do: read. There is no function here, or anywhere the agent can
reach, that changes a limit, restores a struck product, signs or makes a cart.
"""
from signoff.engine import state


def money(cents):
    return None if cents is None else "$%.2f" % (cents / 100)


def _candidate(c):
    out = {"title": c["product"]["title"], "store": c["product"]["store"], "price": money(c["product"]["price_cents"]),
           "product_key": c["product"]["product_key"], "status": c["status"], "picked": c["picked"]}
    if c["reason"]:
        out["reason"] = c["reason"]
    if c["status"] in ("inside", "outside"):
        out["sums"] = ["%s: %s" % (k["name"], k["expr"]) for k in c["checks"]]
        out["store_states"] = [t["quote"] for k in c["checks"] for t in k["terms"] if t.get("quote")]
    out["delivery_time"] = c["arrival"]["quote"] or "not stated by the store"
    return out


def read_state(source=state) -> dict:
    """The sheet as it stands: who set what, each line's status and pick, what is struck, the seal."""
    s = source.get_state()
    sheet, facts = s["sheet"], {f["id"]: f for f in s["sheet"]["shopper_facts"]}
    limits = {line["id"]: line["limits"] for line in sheet["lines"]}
    lines = []
    for line in s["lines"]:
        pick = next((c for c in line["candidates"] if c["picked"]), None)
        lines.append({
            "line_id": line["line_id"], "need": line["need"], "room": line["room"], "status": line["status"],
            "reason": line["reason"],
            "limits": [{"name": l["name"], "rule": "%s %s %g %s" % (
                " + ".join(t.get("figure", t.get("fact", "")).replace("_", " ") for t in l["terms"]), l["op"],
                l["bound"]["value"] if l["bound"]["source"] == "issuer" else facts[l["bound"]["fact"]]["value"], l["unit"]),
                "bound_set_by": sheet["issuer"]["name"] if l["bound"]["source"] == "issuer" else sheet["shopper"]["name"]}
                for l in limits[line["line_id"]]],
            "pick": _candidate(pick) if pick else None,
            "tightest": line["tightest"] and "%s: %s" % (line["tightest"]["name"], line["tightest"]["text"]),
            "counts": line["why"],
            "struck": [{"product_key": k["product_key"], "by": sheet["issuer"]["name"], "reason": k["reason"]}
                       for k in line["struck"]]})
    return {"sheet": sheet["title"], "invented": sheet.get("invented_note"),
            "issuer": "%s (%s)" % (sheet["issuer"]["name"], sheet["issuer"]["role_label"]),
            "shopper": "%s (%s)" % (sheet["shopper"]["name"], sheet["shopper"]["role_label"]),
            "need_by": sheet["need_by"], "pick_rule": sheet["pick_rule"]["label"],
            "shopper_measurements": [{"label": f["label"], "value": "%g %s" % (f["value"], f["unit"])}
                                     for f in sheet["shopper_facts"]],
            "seal": s["seal"]["text"], "total_of_picks": money(s["total_cents"]), "counts": s["counts"],
            "lines": lines}


def read_candidates(line_id: str, source=state) -> dict:
    """Every product found for one line, with its status and the reason code gave."""
    s = source.get_state()
    line = next((l for l in s["lines"] if l["line_id"] == line_id), None)
    if line is None:
        return {"error": "no line %s" % line_id}
    pick = next((c["product"]["price_cents"] for c in line["candidates"] if c["picked"]), None)
    out = []
    for c in sorted(line["candidates"], key=lambda c: (c["product"]["price_cents"], c["id"])):  # cheapest first
        row = _candidate(c)
        if pick is not None and not c["picked"]:  # the comparison is code's, so the model need not make it
            price = c["product"]["price_cents"]
            row["price_against_pick"] = "cheaper" if price < pick else ("dearer" if price > pick else "same price")
        out.append(row)
    return {"line_id": line_id, "need": line["need"], "order": "cheapest first", "candidates": out}


TOOLS = {"read_state": read_state, "read_candidates": read_candidates}
