"""One item's run as a graph that grows, stage by stage. Pure: records in, nodes, edges and stages out.

The page draws what this returns and decides nothing: which products exist, what each page states, which rule
set a product aside and why, which were searched on the web, the order they are ranked in, and whether the
approver has signed all come from the records. A stage whose records do not exist is left out, never invented.
"""
from signoff.graph import build

ASIDE = {"outside": "fail", "unclear": "unclear", "not_stated": "not_stated"}
WORDS = {"outside": "outside", "unclear": "unclear", "not_stated": "not stated", "struck": "struck"}


def _plural(n, one, many=None):
    return "%d %s" % (n, one if n == 1 else (many or one + "s"))


def explore(records: dict, line_id: str, reviews: dict | None = None) -> dict | None:
    state = records["state"]
    sheet = state.get("sheet") or {}
    g = build.build(state, records["receipts"], records["order_text"], records["memory"])
    by_id = {n["id"]: n for n in g["nodes"]}
    line = next((l for l in sheet.get("lines") or [] if l["id"] == line_id), None)
    run = next((l for l in state.get("lines") or [] if l["line_id"] == line_id), None)
    if line is None or run is None or "item:" + line_id not in by_id:
        return None
    item = "item:" + line_id
    limits = [n for n in g["nodes"] if n["kind"] == "limit" and n.get("line_id") == line_id]
    products = [n for n in g["nodes"] if n["kind"] == "product" and n.get("line_id") == line_id]
    statements = [n for n in g["nodes"] if n["kind"] == "statement" and n.get("line_id") == line_id]
    product_ids = {p["id"] for p in products}
    facts = [e["to"] for e in g["edges"] if e["verb"] == "requires" and e["from"] in {l["id"] for l in limits}
             and by_id[e["to"]]["kind"] == "home_fact"]
    stores = sorted({e["to"] for e in g["edges"] if e["verb"] == "sold by" and e["from"] in product_ids})
    people = [i for i in ("person:issuer", "person:shopper") if i in by_id]
    extra, edges = {}, []

    # what each product's page states for each rule, and the rule that set it aside
    checks = {"product:" + c["id"]: {k["limit_id"]: k.get("state") for k in c.get("checks") or []} for c in run.get("candidates") or []}
    aside = {}
    for p in products:
        status = p.get("status")
        if status == "inside":
            continue
        wanted = ASIDE.get(status)
        at = next((l["id"] for l in limits if checks.get(p["id"], {}).get(l["id"].split(":", 1)[1]) == wanted), None)
        aside[p["id"]] = {"reason": WORDS.get(status, status), "limit": at or (limits[-1]["id"] if limits else None),
                          "why": p.get("reason")}

    # the searches: the item's own queries, to each store that returned something
    for s in stores:
        n = sum(1 for p in products if "store:" + p["owner"] == s)
        edges.append({"from": item, "verb": "searches", "to": s, "owner": "system", "label": ", ".join(line.get("queries") or []),
                      "count": n, "source": {"record": "sheet", "file": "sheets/%s.json" % sheet.get("id"), "pointer": "/lines/%s/queries" % line_id}})

    # the web: only what the reviews route recorded
    searched = [c for c in (reviews or {}).get("candidates") or [] if c.get("searched") and "product:" + str(c.get("candidate_id")) in product_ids]
    web_added = []
    if searched:
        rows = sorted({c["ledger_row"] for c in searched if c.get("ledger_row") is not None})
        extra["web:search"] = {"id": "web:search", "kind": "web", "label": "web search", "owner": "system",
                               "sub": "only the title is sent", "text": "\n".join(c.get("query") or "" for c in searched),
                               "source": {"record": "ledger", "rows": rows, "route": "/api/egress"}}
        web_added.append("web:search")
        for c in searched:
            pid = "product:" + c["candidate_id"]
            src = next((s for s in c.get("sources") or [] if s.get("url")), None) or (c.get("sentence") or {})
            if not src.get("url"):
                continue
            rated = c.get("rating") is not None
            label = "%s · %s" % (("%g" % c["rating"]), c.get("review_count")) if rated else "a review"
            rid = "review:" + c["candidate_id"]
            extra[rid] = {"id": rid, "kind": "review", "owner": "web", "label": label,
                          "sub": c.get("rating_site") or src.get("site"), "text": (c.get("sentence") or {}).get("quote") or src.get("quote") or c.get("note"),
                          "quote": (c.get("sentence") or {}).get("quote") or src.get("quote"), "rating": c.get("rating"), "out_of": c.get("out_of"),
                          "review_count": c.get("review_count"), "product": pid,
                          "source": {"record": "web_page", "url": src["url"], "fetched_at": c.get("fetched_at")}}
            web_added.append(rid)
            edges.append({"from": "web:search", "verb": "searches", "to": pid, "owner": "system", "source": extra["web:search"]["source"]})
            edges.append({"from": rid, "verb": "rates", "to": pid, "owner": "web", "source": extra[rid]["source"]})

    # the ranking: the order the engine's own ordering gives. For "cheapest" that is the price; for any other
    # ordering the engine's rank is used when a candidate carries one, and the reply says which was used.
    rule = sheet.get("pick_rule") or {}
    cands = {"product:" + c["id"]: c for c in run.get("candidates") or []}
    passing = [p for p in products if p.get("status") == "inside"]
    if all(isinstance(cands[p["id"]].get("rank"), (int, float)) for p in passing) and passing:
        passing.sort(key=lambda p: cands[p["id"]]["rank"])
        ranked_by = "the engine's rank"
    else:
        passing.sort(key=lambda p: (not p.get("picked"), p.get("price_cents") or 0))
        ranked_by = "price" if rule.get("id") == "cheapest" else "the pick first, then price (the engine gives no rank for %r)" % rule.get("id")
    for p in products:
        c = cands[p["id"]]
        p["image_url"] = (c.get("product") or {}).get("image_url")
        p["picked_because"] = c.get("picked_because")
        p["preferences"] = c.get("preferences")
        p["checks"] = checks.get(p["id"], {})
        p["aside"] = aside.get(p["id"])

    # the signature and what lies beyond it
    seal = state.get("seal") or {}
    issuer = sheet.get("issuer") or {}
    signed = build._last(records["receipts"], "signed", sheet_hash=seal.get("sheet_hash")) if seal.get("signed") else None
    extra["gate"] = {"id": "gate", "kind": "gate", "owner": "issuer", "label": "%s signs" % (issuer.get("role") or "approver").capitalize(),
                     "sub": "signed %s" % str(seal.get("signed_at") or "")[11:16] if seal.get("signed") else "not signed",
                     "open": bool(seal.get("signed")), "href": "/seal/", "text": seal.get("text"),
                     "source": build._receipt(signed) if signed else {"record": "sheet", "file": "sheets/%s.json" % sheet.get("id"), "pointer": "/issuer"}}
    pick = next((p["id"] for p in products if p.get("picked")), None)
    if pick:
        edges.append({"from": pick, "verb": "waits for", "to": "gate", "owner": "system", "source": extra["gate"]["source"]})
    carts = [c for c in seal.get("carts") or [] if any(c.get("store") == p["owner"] for p in products if p.get("picked"))]
    made = build._last(records["receipts"], "carts_created", sheet_hash=seal.get("sheet_hash")) or build._last(records["receipts"], "carts_updated", sheet_hash=seal.get("sheet_hash"))
    cart_ids = []
    if seal.get("signed") and made:
        for c in carts:
            cid = "cart:%s" % c.get("store")
            extra[cid] = {"id": cid, "kind": "cart", "owner": c.get("store"), "label": "cart", "sub": c.get("store"),
                          "text": c.get("cart_url") or c.get("cart_id"), "source": build._receipt(made)}
            edges.append({"from": "gate", "verb": "releases", "to": cid, "owner": "issuer", "source": build._receipt(made)})
            cart_ids.append(cid)

    keep = set(people) | {item} | set(facts) | {l["id"] for l in limits} | set(stores) | product_ids | {s["id"] for s in statements}
    edges = [e for e in g["edges"] if e["from"] in keep and e["to"] in keep] + edges

    # the stages, in the order the run happened
    stated = sum(1 for p in products if all(v != "not_stated" for v in checks.get(p["id"], {}).values()))
    fetched = sorted(str((cands[p["id"]].get("product") or {}).get("fetched_at") or "") for p in products)
    stages = [
        {"id": "order", "title": "The order", "at": (state.get("order") or {}).get("derived_at"),
         "caption": "%s wrote the order; %s measured the house." % (issuer.get("name"), (sheet.get("shopper") or {}).get("name")) if facts
         else "%s wrote the order." % issuer.get("name"),
         "node_ids_added": people + [item] + facts, "node_ids_set_aside": [], "reason_counts": {}},
        {"id": "search", "title": "The search", "at": next((f for f in fetched if f), None),
         "caption": "%s searched: %s found." % (_plural(len(stores), "store"), _plural(len(products), "option")),
         "node_ids_added": stores + [p["id"] for p in products], "node_ids_set_aside": [], "reason_counts": {}},
        {"id": "reading", "title": "The reading", "at": (state.get("readers") or {}).get("made_at"),
         "caption": "Every page read: %d of %d state every figure." % (stated, len(products)),
         "node_ids_added": [s["id"] for s in statements], "node_ids_set_aside": [], "reason_counts": {},
         "not_stated": [p["id"] for p in products if any(v == "not_stated" for v in checks.get(p["id"], {}).values())]},
    ]
    left = len(products)
    for l in limits:
        out = [pid for pid, a in aside.items() if a["limit"] == l["id"]]
        counts = {}
        for pid in out:
            counts[aside[pid]["reason"]] = counts.get(aside[pid]["reason"], 0) + 1
        left -= len(out)
        stages.append({"id": "rule:" + l["id"], "title": "The rules", "at": None, "limit": l["id"], "rule": l["label"],
                       "caption": "%s: %d set aside, %d left." % (str(l.get("sub") or l["label"]).capitalize(), len(out), left),
                       "node_ids_added": [l["id"]], "node_ids_set_aside": out, "reason_counts": counts})
    if web_added:
        rated = sum(1 for i in web_added if (extra[i].get("rating") is not None))
        stages.append({"id": "web", "title": "The web", "at": min((c.get("fetched_at") or "" for c in searched), default=None) or None,
                       "caption": "%s searched on the web; %d rated." % (_plural(len(searched), "passing product"), rated),
                       "node_ids_added": web_added, "node_ids_set_aside": [], "reason_counts": {}})
    stages.append({"id": "ranking", "title": "The ranking", "at": None,
                   "caption": "%d pass, ranked: %s." % (len(passing), rule.get("label") or rule.get("id")),
                   "node_ids_added": [], "node_ids_set_aside": [], "reason_counts": {},
                   "order": [p["id"] for p in passing], "ranked_by": ranked_by, "pick_rule": rule})
    stages.append({"id": "signature", "title": "The signature", "at": seal.get("signed_at"),
                   "caption": ("Signed: %s." % _plural(len(cart_ids), "cart") + " created") if seal.get("signed")
                   else "Nothing is bought until %s signs." % issuer.get("name"),
                   "node_ids_added": ["gate"] + cart_ids, "node_ids_set_aside": [], "reason_counts": {}})
    nodes = [by_id[i] for i in people + [item] + facts + stores] + products + statements + limits + list(extra.values())
    return {"line_id": line_id, "need": line.get("need"), "nodes": nodes, "edges": edges, "stages": stages,
            "totals": {"products": len(products), "passing": len(passing), "set_aside": len(aside),
                       "pages": len({(cands[p["id"]].get("product") or {}).get("product_id") for p in products})},
            "reviews_available": reviews is not None}
