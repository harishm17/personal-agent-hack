"""Put each owner's part of the graph into that owner's Cognee dataset, build Cognee's graph, and time it.

Run: SIGNOFF_GRAPH_FROM=http://127.0.0.1:8800 uv run python -m signoff.graph.sync [--all]

Each owner's sentences are written with that owner's identity (issuer, shopper) or, for what the stores'
pages state and what the checks worked out, with the account's. Without --all only what the item views show
is sent (the pick, the nearest products not chosen and the statements that decided them); --all sends every
product and statement.
"""
import json
import sys
import time

from signoff.graph import build, cognee, records


def _where(source: dict) -> str:
    kind = source.get("record")
    if kind == "order":
        return "Source: the order document %s, characters %s to %s." % (source["file"], source["start"], source["end"])
    if kind == "sheet":
        return "Source: the sheet file %s at %s." % (source["file"], source["pointer"])
    if kind == "receipt":
        return "Source: receipt %s (%s) of %s." % (source["hash"][:12], source["type"], source["at"])
    if kind == "store_page":
        span = ", characters %s to %s" % (source["start"], source["end"]) if "start" in source else ""
        return "Source: the store's page %s%s, fetched %s." % (source["url"], span, source.get("fetched_at"))
    if kind == "store_answer":
        return "Source: the store's own agent, asked %s." % source["asked_at"]
    return "Source: %s." % json.dumps(source, sort_keys=True)


def sentences(graph: dict, people: dict) -> dict:
    """{owner: [sentence, ...]}: one sentence per node or edge, in the owner's dataset, each ending with its source."""
    nodes = {n["id"]: n for n in graph["nodes"]}
    out: dict[str, list[str]] = {}

    def say(owner, text):
        out.setdefault(owner, []).append(text)

    def name(owner):
        return people.get(owner) or owner

    item_of = {n.get("line_id"): n for n in graph["nodes"] if n["kind"] == "order_item"}
    for n in graph["nodes"]:
        item = (item_of.get(n.get("line_id")) or {}).get("label")
        if n["kind"] == "order_item":
            say("issuer", '%s wrote the order item "%s" (%s): "%s" %s' % (name("issuer"), n["label"], n.get("sub"), n.get("text"), _where(n["source"])))
        elif n["kind"] == "limit":
            say("issuer", '%s set the limit "%s" on the %s: %s. The order says: "%s" %s'
                % (name("issuer"), n["label"], item, n.get("sub"), n.get("text"), _where(n["source"])))
        elif n["kind"] == "home_fact":
            say("shopper", "%s measured at the house: %s. %s" % (name("shopper"), n.get("text"), _where(n["source"])))
        elif n["kind"] == "product":
            say(n["owner"], '%s sells "%s" (%s), a candidate for the %s. %s' % (n["owner"], n["label"], n.get("sub"), item, _where(n["source"])))
            outcome = "is the pick for" if n.get("picked") else "was not chosen for"
            why = "" if n.get("picked") else " Status: %s%s." % ((n.get("status") or "").replace("_", " "), ", " + n["reason"] if n.get("reason") else "")
            say("system", 'The product "%s" (%s) sold by %s %s the %s.%s %s' % (n["label"], n.get("sub"), n["owner"], outcome, item, why, _where(n["source"])))
        elif n["kind"] == "strike":
            say("issuer", '%s struck a product from the %s. Reason: "%s" %s' % (name("issuer"), item, n.get("text"), _where(n["source"])))
        elif n["kind"] == "purchase":
            say("issuer", "%s signed the sheet: %s %s" % (name("issuer"), n.get("text"), _where(n["source"])))
        elif n["kind"] == "statement" and n.get("topic"):
            say(n["owner"], '%s states about %s: "%s" %s' % (n["owner"], n["topic"], n.get("quote"), _where(n["source"])))
    for e in graph["edges"]:
        a, b = nodes[e["from"]], nodes[e["to"]]
        if e["verb"] == "states" and a["kind"] == "product":
            say(b["owner"], 'The page of %s for "%s" (%s) states its %s: "%s" That is %s. %s'
                % (b["owner"], a["label"], a.get("sub"), b.get("sub"), b.get("quote"), b["label"], _where(b["source"])))
        elif e["verb"] in ("passes", "fails", "unclear") and a["kind"] == "statement":
            product = next((nodes[x["from"]] for x in graph["edges"] if x["to"] == a["id"] and x["verb"] == "states"), None)
            verb = {"passes": "passes", "fails": "fails", "unclear": "is unclear against"}[e["verb"]]
            say("system", 'For the %s, the %s that %s states for "%s" (%s) %s the limit "%s" (%s)%s. %s'
                % ((item_of.get(b.get("line_id")) or {}).get("label"), a.get("sub"), a["owner"], (product or {}).get("label"), a["label"], verb,
                   b["label"], b.get("sub"), ": " + a["why"] if a.get("why") else "", _where(a["source"])))
        elif e["verb"] == "does not state":
            say("system", 'For the %s, the page of %s for "%s" does not state what the limit "%s" needs, so it is not bought on a guess. %s'
                % ((item_of.get(b.get("line_id")) or {}).get("label"), a["owner"], a["label"], b["label"], _where(e["source"])))
    return out


def main(everything: bool = False) -> dict:
    r = records.read()
    graph = build.build(r["state"], r["receipts"], r["order_text"], r["memory"])
    sheet = r["state"]["sheet"]
    people = {role: "%s (%s)" % (sheet[role]["name"], sheet[role].get("role_label")) for role in ("issuer", "shopper") if sheet.get(role)}
    if everything:
        part = graph
    else:
        seen, part = set(), {"nodes": [], "edges": []}
        for line in sheet["lines"]:
            v = build.view(graph, line["id"])
            part["nodes"] += [n for n in v["nodes"] if n["id"] not in seen]
            seen |= {n["id"] for n in v["nodes"]}
            part["edges"] += [e for e in v["edges"] if e not in part["edges"]]
    texts = sentences(part, people)
    owners = sorted(texts)
    cognee.setup(owners)
    started = time.monotonic()
    writes = []
    for owner in owners:
        identity = owner if owner in ("issuer", "shopper") else "system"
        w = cognee.write(identity, owner, ["\n".join(texts[owner])], "%d sentences from the graph%s" % (len(texts[owner]), " (everything)" if everything else " (what the item views show)"))
        writes.append({k: w[k] for k in ("identity", "dataset", "status", "accepted", "seconds")} | {"sentences": len(texts[owner])})
        print(writes[-1], flush=True)
    added = round(time.monotonic() - started, 1)
    cognee.cognify(owners, background=True)
    state = {}
    while time.monotonic() - started < 1500:
        time.sleep(10)
        state = cognee.status(owners)
        print(round(time.monotonic() - started), state, flush=True)
        if all("COMPLETED" in v or "ERRORED" in v for v in state.values()):
            break
    total = round(time.monotonic() - started, 1)
    sizes = {}
    for owner in owners:
        try:
            sizes[owner] = cognee.graph_size(owner)
        except Exception as error:  # noqa: BLE001
            sizes[owner] = {"error": type(error).__name__}
    run = {"at": cognee._now(), "scope": "everything" if everything else "what the item views show",
           "sheet_id": sheet["id"], "sentences": {o: len(texts[o]) for o in owners}, "writes": writes,
           "seconds_adding": added, "seconds_total": total, "status": state, "cognee_graph": sizes,
           "own_graph": build.counts(part)}
    held = cognee.facts()
    cognee._save_facts({"ingests": (held.get("ingests") or []) + [run]})
    cognee.log({"action": "ingest", "identity": "owners", "scope": run["scope"], "seconds": total,
                "status": 200 if all("COMPLETED" in v for v in state.values()) else 500, "reply": json.dumps(state)[:300]})
    print(json.dumps(run, indent=1))
    return run


if __name__ == "__main__":
    main(everything="--all" in sys.argv)
