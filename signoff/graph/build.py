"""The run's knowledge as one graph, built only from records that already exist.

Input: the body of GET /api/state, the receipt chain, the order document's text and, when the MEMORY stream has
rows, those. Output: nodes and edges. Every node and every edge carries its owner (issuer, shopper, a store's
domain, or system) and its source (a file with an offset or a pointer, a store page with an offset, or a
receipt hash). Nothing is added without a source: a record that names none is left out and counted in `skipped`.

Pure functions: no file, network or engine access here (see records.py for the reading).
"""

KINDS = ("person", "store", "order_item", "home_fact", "limit", "statement", "product", "strike", "purchase")
VERBS = ("wrote", "measured", "requires", "states", "sold by", "passes", "fails", "unclear", "does not state",
         "struck", "signed", "covers")
# The picture's five columns, left to right.
COLUMNS = ("who", "what they said", "the rule", "the product's own words", "the outcome")
COLUMN_OF = {"person": 0, "store": 0, "order_item": 1, "home_fact": 1, "limit": 2, "statement": 3,
             "product": 4, "strike": 4, "purchase": 4}
OPS = {">=": "at least", "<=": "at most", "==": "exactly", ">": "more than", "<": "less than"}
CHECK_VERB = {"pass": "passes", "fail": "fails", "unclear": "unclear"}


class Graph:
    def __init__(self):
        self.nodes, self.edges, self.skipped = {}, [], []

    def node(self, id, kind, label, owner, source, **more):
        if not source:
            self.skipped.append({"id": id, "kind": kind, "why": "no source record"})
            return None
        self.nodes[id] = dict({"id": id, "kind": kind, "column": COLUMN_OF[kind], "label": label,
                               "owner": owner, "source": source}, **{k: v for k, v in more.items() if v is not None})
        return id

    def edge(self, a, verb, b, owner, source):
        if a in self.nodes and b in self.nodes and source:
            self.edges.append({"from": a, "verb": verb, "to": b, "owner": owner, "source": source})

    def body(self):
        return {"nodes": list(self.nodes.values()), "edges": self.edges, "skipped": self.skipped}


def _num(value):
    return ("%g" % value) if isinstance(value, (int, float)) else str(value)


def _money(cents):
    return "$%d.%02d" % divmod(int(cents), 100) if cents is not None else None


def _receipt(r):
    return {"record": "receipt", "hash": r["hash"], "n": r["n"], "type": r["type"], "at": r["at"]}


def _last(receipts, kind, **detail):
    """The newest receipt of this type whose detail has these values."""
    for r in reversed(receipts or []):
        d = r.get("detail") or {}
        if r.get("type") == kind and all(d.get(k) == v for k, v in detail.items()):
            return r
    return None


def _order_line(order_text, spans):
    """The line of the order document that encloses these quoted spans, as (start, end), or None."""
    if not order_text or not spans:
        return None
    lo, hi = min(s for s, _ in spans), max(e for _, e in spans)
    start = order_text.rfind("\n", 0, lo) + 1
    end = order_text.find("\n", hi)
    end = len(order_text) if end < 0 else end
    return (start, end) if "\n" not in order_text[start:end] else None


def _stated(term):
    """A figure as the page states it: "440 lb", "12 or 16 in"."""
    values = term.get("values") or ([term["value"]] if term.get("value") is not None else [])
    return (" or ".join(_num(v) for v in values) + " " + (term.get("unit") or "")).strip()


def build(state: dict, receipts: list | None = None, order_text: str | None = None,
          memory: list | None = None, sheet_file: str | None = None) -> dict:
    g = Graph()
    sheet = state.get("sheet") or {}
    receipts = receipts or []
    sheet_file = sheet_file or "sheets/%s.json" % sheet.get("id")
    order_doc = sheet.get("order_doc") or (state.get("order") or {}).get("doc")

    def in_sheet(pointer):
        return {"record": "sheet", "file": sheet_file, "pointer": pointer}

    # who
    for role in ("issuer", "shopper"):
        p = sheet.get(role)
        if p:
            g.node("person:" + role, "person", p.get("name") or role, role, in_sheet("/" + role),
                   sub=p.get("role_label") or p.get("role"), text="%s, %s" % (p.get("name"), p.get("role_label") or role))
    for i, domain in enumerate(sheet.get("stores") or []):
        g.node("store:" + domain, "store", domain, domain, in_sheet("/stores/%d" % i), sub="store")

    # what the shopper measured
    facts = {}
    for i, f in enumerate(sheet.get("shopper_facts") or []):
        r = _last(receipts, "shopper_fact", fact_id=f["id"])
        source = _receipt(r) if r else in_sheet("/shopper_facts/%d" % i)
        value = "%s %s" % (_num(f.get("value")), f.get("unit") or "")
        facts[f["id"]] = g.node("fact:" + f["id"], "home_fact", "%s %s" % (f.get("short") or f.get("label"), value),
                                "shopper", source, sub="measured at the house",
                                text="%s: %s" % (f.get("label"), value), value=f.get("value"), unit=f.get("unit"))
        g.edge("person:shopper", "measured", facts[f["id"]], "shopper", source)

    # the order: items and their limits
    for li, line in enumerate(sheet.get("lines") or []):
        spans = [(lim["from_order"]["start"], lim["from_order"]["end"]) for lim in line.get("limits") or []
                 if (lim.get("from_order") or {}).get("span_found_in_text")]
        whole = _order_line(order_text, spans)
        if whole and order_doc:
            source = {"record": "order", "file": order_doc, "start": whole[0], "end": whole[1]}
            text = order_text[whole[0]:whole[1]]
        else:
            source, text = in_sheet("/lines/%d" % li), line.get("need")
        item = g.node("item:" + line["id"], "order_item", line.get("need"), "issuer", source,
                      sub=line.get("room"), text=text, line_id=line["id"])
        g.edge("person:issuer", "wrote", item, "issuer", source)
        for mi, lim in enumerate(line.get("limits") or []):
            fo, bound = lim.get("from_order") or {}, lim.get("bound") or {}
            changed = _last(receipts, "limit_set", limit_id=lim["id"])
            if changed:
                source = _receipt(changed)
            elif fo.get("span_found_in_text") and order_doc:
                source = {"record": "order", "file": fo.get("doc") or order_doc, "start": fo["start"], "end": fo["end"]}
            else:
                source = in_sheet("/lines/%d/limits/%d" % (li, mi))
            fact = facts.get(bound.get("fact"))
            against = g.nodes[fact]["label"] if fact else "%s %s" % (_num(bound.get("value")), lim.get("unit") or "")
            node = g.node("limit:" + lim["id"], "limit", lim.get("name"), "issuer", source,
                          sub="%s %s" % (OPS.get(lim.get("op"), lim.get("op")), against),
                          text=fo.get("quote") or lim.get("label"), line_id=line["id"], op=lim.get("op"))
            g.edge(item, "requires", node, "issuer", source)
            if fact:
                g.edge(node, "requires", fact, "issuer", source)

    # what the stores' pages state, and what came of it
    for line in state.get("lines") or []:
        for c in line.get("candidates") or []:
            p = c.get("product") or {}
            store = p.get("store")
            page = {"record": "store_page", "url": p.get("url"), "fetched_at": p.get("fetched_at")} if p.get("url") else None
            price = _money(p.get("price_cents"))
            option = p.get("variant_title") if (c.get("variants") or 0) > 1 else None  # an option's name says something only when there is a choice
            pid = g.node("product:" + c["id"], "product", p.get("title"), store, page,
                         sub=" · ".join(x for x in (price, option) if x),
                         text=p.get("title"), line_id=line["line_id"], status=c.get("status"),
                         picked=bool(c.get("picked")), reason=c.get("reason"), price_cents=p.get("price_cents"),
                         product_key=p.get("product_key"))
            if not pid:
                continue
            if "store:%s" % store not in g.nodes:  # a store the sheet does not list is known from its own page
                g.node("store:%s" % store, "store", store, store, page, sub="store")
            g.edge(pid, "sold by", "store:%s" % store, store, page)
            for check in c.get("checks") or []:
                limit = "limit:" + check["limit_id"]
                quoted = [t for t in check.get("terms") or [] if t.get("quote") and t.get("start") is not None]
                if check.get("state") == "not_stated" or not quoted:
                    g.edge(pid, "does not state", limit, store, page)
                    continue
                for t in quoted:
                    source = dict(page, start=t["start"], end=t["end"])
                    sid = g.node("statement:%s:%s:%s" % (c["id"], check["limit_id"], t.get("figure")), "statement",
                                 _stated(t), store, source, sub=t.get("label"), text=t.get("sentence") or t["quote"],
                                 quote=t["quote"], quote_in_text=t.get("quote_in_sentence"), line_id=line["line_id"],
                                 state=check.get("state"), expr=check.get("expr"), why=check.get("unclear_why"),
                                 more_on_page=(t.get("statements") or 1) - 1 or None)
                    g.edge(pid, "states", sid, store, source)
                    g.edge(sid, CHECK_VERB.get(check.get("state"), "unclear"), limit, "system", source)
        for s in line.get("struck") or []:
            r = _last(receipts, "strike", line_id=s.get("line_id"), product_key=s.get("product_key"))
            source = _receipt(r) if r else None
            sid = g.node("strike:%s:%s" % (line["line_id"], s.get("product_key")), "strike", "struck", "issuer", source,
                         sub=s.get("at"), text=s.get("reason"), line_id=line["line_id"])
            if sid:
                g.edge("person:issuer", "struck", sid, "issuer", source)
                for n in list(g.nodes.values()):
                    if n["kind"] == "product" and n.get("line_id") == line["line_id"] and n.get("product_key") == s.get("product_key"):
                        g.edge(sid, "struck", n["id"], "issuer", source)

    # the stores' answers on delivery and returns
    for a in state.get("store_answers") or []:
        store = a.get("store")
        for topic in ("delivery", "returns"):
            quote = (a.get(topic) or {}).get("quote")
            if not quote or not a.get("asked_at"):
                continue
            source = {"record": "store_answer", "store": store, "asked_at": a["asked_at"],
                      "start": (a.get("answer") or "").find(quote), "end": (a.get("answer") or "").find(quote) + len(quote)}
            sid = g.node("statement:answer:%s:%s" % (store, topic), "statement", topic, store, source,
                         sub="the store's agent", text=a.get("answer"), quote=quote, topic=topic)
            g.edge("store:%s" % store, "states", sid, store, source)

    # the signature
    seal = state.get("seal") or {}
    if seal.get("signed"):
        r = _last(receipts, "signed", sheet_hash=seal.get("sheet_hash"))
        source = _receipt(r) if r else None
        total = _money(state.get("total_cents"))
        sid = g.node("purchase:" + str(seal.get("sheet_hash")), "purchase", "signed", "issuer", source,
                     sub=total, text=seal.get("text"), carts=len(seal.get("carts") or []))
        if sid:
            g.edge("person:issuer", "signed", sid, "issuer", source)
            for n in list(g.nodes.values()):
                if n["kind"] == "product" and n.get("picked"):
                    g.edge(sid, "covers", n["id"], "issuer", source)

    # what is remembered from earlier runs (the MEMORY stream's rows): each keeps its own owner and source
    kind_of = {"home_measurement": ("home_fact", "measured"), "strike": ("strike", "struck"),
               "store_answer": ("statement", "states"), "purchase": ("purchase", "signed")}
    for row in memory or []:
        kind, verb = kind_of.get(row.get("kind"), (None, None))
        owner = row.get("owner")
        who = "person:" + owner if owner in ("issuer", "shopper") else "store:%s" % owner
        if not kind or who not in g.nodes:
            g.skipped.append({"id": "memory:%s" % row.get("id"), "kind": row.get("kind"), "why": "unknown kind or owner"})
            continue
        source = dict(row["source"], record="memory", memory_id=row.get("id")) if isinstance(row.get("source"), dict) and row["source"] else None
        mid = g.node("memory:%s" % row.get("id"), kind, str(row.get("key") or row.get("kind")), owner, source,
                     sub="remembered", text=row.get("text"), remembered=True, sheet_id=row.get("sheet_id"))
        if mid:
            g.edge(who, verb, mid, owner, source)

    return g.body()


def view(graph: dict, line_id: str, near: int = 2) -> dict | None:
    """One item's part of the graph, small enough to read: the item, its limits, the home facts they use, the
    pick, the `near` cheapest other products that were not chosen (one option per product), every struck
    product, and for each shown product the statements that decided it. The rest is folded into counts."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    if "item:" + line_id not in nodes:
        return None
    products = [n for n in nodes.values() if n["kind"] == "product" and n.get("line_id") == line_id]
    picks = [p for p in products if p.get("picked")]
    struck = {e["to"] for e in graph["edges"] if e["verb"] == "struck" and e["to"] in nodes and nodes[e["to"]]["kind"] == "product"}
    shown = {p["id"]: p for p in picks}
    shown.update({p["id"]: p for p in products if p["id"] in struck})
    taken = {p.get("product_key") for p in shown.values()}
    rejected = sorted((p for p in products if p.get("status") != "inside" and p["id"] not in shown),
                      key=lambda p: (p.get("price_cents") is None, p.get("price_cents") or 0))
    for p in rejected:
        if near <= 0:
            break
        if p.get("product_key") in taken:
            continue
        taken.add(p.get("product_key"))
        shown[p["id"]] = p
        near -= 1

    keep = {"item:" + line_id, "person:issuer", "person:shopper"} | set(shown)
    keep |= {n["id"] for n in nodes.values() if n["kind"] == "limit" and n.get("line_id") == line_id}
    for e in graph["edges"]:
        if e["from"] in keep and nodes[e["from"]]["kind"] == "limit" and nodes[e["to"]]["kind"] == "home_fact":
            keep.add(e["to"])
        if e["from"] in shown and e["verb"] == "sold by":
            keep.add(e["to"])
        if e["to"] in shown and nodes[e["from"]]["kind"] in ("strike", "purchase"):
            keep.add(e["from"])
    for e in graph["edges"]:
        if e["from"] in shown and e["verb"] == "states":
            s = nodes[e["to"]]
            # the pick is decided by every figure it passes; a product not chosen by the figures that stopped it
            if shown[e["from"]].get("picked") or shown[e["from"]].get("status") == "inside" or s.get("state") != "pass":
                keep.add(s["id"])
    keep &= set(nodes)
    # nobody floats: a person or store stays only if something shown is tied to them
    tied = {x for e in graph["edges"] if e["from"] in keep and e["to"] in keep for x in (e["from"], e["to"])}
    keep = {i for i in keep if nodes[i]["kind"] not in ("person", "store") or i in tied}
    folded = {}
    for p in products:
        if p["id"] not in shown:
            folded[p.get("status") or "unknown"] = folded.get(p.get("status") or "unknown", 0) + 1
    return {"line_id": line_id,
            "nodes": [n for n in graph["nodes"] if n["id"] in keep],
            "edges": [e for e in graph["edges"] if e["from"] in keep and e["to"] in keep],
            "folded": {"products": sum(folded.values()), "by_status": folded,
                       "rule": "shown: the pick, struck products, and the %d cheapest other products not chosen" % len([p for p in shown.values() if not p.get("picked") and p["id"] not in struck])},
            "columns": list(COLUMNS)}


def counts(graph: dict) -> dict:
    by_kind, by_owner, by_verb = {}, {}, {}
    for n in graph["nodes"]:
        by_kind[n["kind"]] = by_kind.get(n["kind"], 0) + 1
        by_owner[n["owner"]] = by_owner.get(n["owner"], 0) + 1
    for e in graph["edges"]:
        by_verb[e["verb"]] = by_verb.get(e["verb"], 0) + 1
    return {"nodes": len(graph["nodes"]), "edges": len(graph["edges"]), "by_kind": by_kind, "by_owner": by_owner,
            "by_verb": by_verb, "skipped": len(graph.get("skipped") or [])}
