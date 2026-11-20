"""What left, and what never did: every class of fact the agent holds in this run against every outside party,
from records only. Read-only.

Two records say what left. The outbound ledger (signoff/obs/egress.py) has one row per payload: who received it,
the classes the sender declared, and what the ledger's own search found in the payload (it can find a limit, a
home measurement and a person's name; it cannot find the other classes, it only has the sender's word for them).
The guard's record (signoff/talk, `GET /api/talk/threads`) has one entry per message drafted for a store's own
agent: the spans it removed, by class, and what it left.

A cell is: `sent` (the sender declared the class), `found` (the ledger's search met it though the sender did not
declare it: shown in red), `stopped` (the guard removed it from a message), `never` (every payload to that party was
checked by something that can find the class, and none held it) or `not_recorded` (no record can tell).
"""
from signoff.trail.feed import CLASS_WORDS, _epoch, _plain

DETECTED = ("limit", "home_measurement", "person")      # what the ledger's own search can find in a payload
# Whose fact each class is: the dot beside the row. A class not listed gets no dot.
OWNER = {"limit": "issuer", "order": "issuer", "need_by": "issuer", "home_measurement": "shopper", "person": "shopper",
         "health": "shopper", "money": "shopper", "address": "shopper", "delivery_region": "shopper",
         "product": "store", "store_text": "store", "price": "store"}
GROUP_OVER = 3      # more stores than this are one column, counted
LISTED = 6          # records listed behind one cell; the rest are counted


def _examples(sheet: dict, flow: dict, messages: list) -> dict:
    """One real value of each class from this run: the sheet, the followed item, the guard's records."""
    sheet, flow = sheet or {}, flow or {}
    said = flow.get("said") or {}
    out = {}
    for line in sheet.get("lines") or []:
        for lim in line.get("limits") or []:
            b = lim.get("bound") or {}
            if b.get("source") == "issuer" and "limit" not in out:
                out["limit"] = ("%g %s" % (b.get("value"), lim.get("unit") or "")).strip()
    for f in sheet.get("shopper_facts") or []:
        out.setdefault("home_measurement", ("%g %s" % (f.get("value"), f.get("unit") or "")).strip())
    names = [n for n in ((sheet.get("issuer") or {}).get("name"), (sheet.get("shopper") or {}).get("name")) if n]
    if names:
        out["person"] = ", ".join(names)
    page = said.get("page") or {}
    if page.get("title"):
        out["product"] = page["title"]
    if page.get("excerpt"):
        e = page["excerpt"][0]
        out["store_text"] = e["text"][e["quote"][0]:e["quote"][1]]
    if page.get("price"):
        out["price"] = page["price"]
    sentences = (said.get("order") or {}).get("sentences") or []
    if sentences:
        out["order"] = sentences[0]["text"]
    for key in ("need_by", "delivery_region"):
        if sheet.get(key):
            out[key] = str(sheet[key])
    for m in messages or []:                      # a class only the guard knows: its own words from a draft
        for r in m.get("removed") or []:
            if r.get("class") and r.get("text"):
                out.setdefault(r["class"], r["text"])
    return out


def build(sheet: dict, flow: dict, rows: list, messages: list, rule: dict = None, marks: dict = None) -> dict:
    """The matrix. `rows`: the ledger's rows of this run; `messages`: the guard's records; `rule`: the sheet's
    sharing rule as the guard reads it (`may`, `sealed`); `marks`: the guard's words for its classes."""
    rows = [r for r in rows or [] if isinstance(r, dict)]
    messages = [m for m in messages or [] if isinstance(m, dict)]
    rule, marks = rule or {}, marks or {}
    examples = _examples(sheet, flow, messages)

    # columns: who received anything
    by_recipient = {}
    for r in rows:
        by_recipient.setdefault((r.get("kind") or "", r.get("recipient") or ""), []).append(r)
    kinds = {}
    for (kind, recipient), rs in by_recipient.items():
        kinds.setdefault(kind, []).append((recipient, rs))
    columns, payloads_of = [], {}
    for kind in ("model", "store", "sponsor service"):
        group = sorted(kinds.get(kind) or [], key=lambda x: -len(x[1]))
        word = {"sponsor service": "service"}.get(kind, kind)
        if kind == "store" and len(group) > GROUP_OVER:   # many stores are one column; every other party has its own
            col = "kind:%s" % kind
            columns.append({"id": col, "label": "%d %ss" % (len(group), word), "kind": word,
                            "payloads": sum(len(rs) for _, rs in group), "members": [name for name, _ in group]})
            payloads_of[col] = [r for _, rs in group for r in rs]
        else:
            for name, rs in group:
                columns.append({"id": name, "label": name.split(":")[-1].split("/")[-1], "kind": word, "payloads": len(rs),
                                "members": [name]})
                payloads_of[name] = rs
    stores = sorted({m.get("store") for m in messages if m.get("store")})
    if messages:      # the stores' own agents first: they are the outside party the sharing rule is about
        columns.insert(0, {"id": "agents", "label": "%d store agent%s" % (len(stores), "" if len(stores) == 1 else "s"),
                        "kind": "store agent", "payloads": len(messages), "members": stores})

    # rows: the classes that exist in this run (an example of it, or a record that carries or stops it)
    seen = {c for r in rows for c in (r.get("declared_classes") or []) + (r.get("fact_classes") or []) if c != "none"}
    seen |= {x.get("class") for m in messages for x in (m.get("removed") or []) + (m.get("left") or []) if x.get("class")}
    order = list(dict.fromkeys(list(rule.get("may") or []) + list(rule.get("sealed") or []) + list(CLASS_WORDS)))
    classes = [c for c in order + sorted(seen - set(order)) if c in seen or examples.get(c)]
    out_rows = [{"id": c, "label": marks.get(c) or CLASS_WORDS.get(c) or _plain(c), "owner": OWNER.get(c),
                 "example": examples.get(c) or "", "sealed": c in (rule.get("sealed") or [])} for c in classes]

    def ledger_item(r, cls=None):
        hits = [h.partition(": ")[2] for h in r.get("sealed_found_in_payload") or [] if h.partition(": ")[0] == cls]
        return {"ledger": r.get("n"), "at": r.get("at"), "purpose": r.get("purpose"), "to": r.get("recipient"),
                "hash": r.get("payload_sha256"), "bytes": r.get("bytes"), "match": ", ".join(sorted(set(hits)))}

    cells = {}
    for c in classes:
        line = {}
        for col in columns:
            if col["id"] == "agents":
                stopped = [m for m in messages if any(x.get("class") == c for x in m.get("removed") or [])]
                left = [m for m in messages if m.get("sent") and any(x.get("class") == c for x in m.get("left") or [])]
                cell = {"checked": len(messages)}
                if stopped:
                    cell.update(stopped=len(stopped), stopped_items=[
                        {"at": m.get("at"), "to": m.get("store"), "decision": _plain(m.get("decision")), "draft": m.get("draft"),
                         "words": [x.get("text") for x in m.get("removed") or [] if x.get("class") == c]} for m in stopped[:LISTED]])
                if left:
                    cell.update(sent=len(left), sent_items=[{"at": m.get("at"), "to": m.get("store"), "purpose": m.get("sent"),
                                                              "match": ", ".join(x.get("text") or "" for x in m.get("left") or [] if x.get("class") == c)}
                                                             for m in left[:LISTED]])
                known = c in (rule.get("may") or []) or c in (rule.get("sealed") or [])     # the guard looks for this class
                cell["state"] = "stopped" if stopped else "sent" if left else ("never" if known else "not_recorded")
            else:
                rs = payloads_of[col["id"]]
                declared = [r for r in rs if c in (r.get("declared_classes") or [])]
                found = [r for r in rs if c not in (r.get("declared_classes") or [])
                         and any(h.partition(": ")[0] == c for h in r.get("sealed_found_in_payload") or [])]
                cell = {"checked": len(rs)}
                if declared:
                    cell.update(sent=len(declared), sent_items=[ledger_item(r, c) for r in declared[-LISTED:]])
                if found:
                    cell.update(found=len(found), found_items=[ledger_item(r, c) for r in found[-LISTED:]])
                cell["state"] = "found" if found else "sent" if declared else ("never" if c in DETECTED else "not_recorded")
            line[col["id"]] = cell
        cells[c] = line

    carried = [r for r in rows if set(DETECTED) & (set(r.get("declared_classes") or []) | {h.partition(": ")[0] for h in r.get("sealed_found_in_payload") or []})]
    times = sorted(t for t in (_epoch(r.get("at")) for r in rows) if t is not None)
    return {
        "sheet": {"id": (sheet or {}).get("id"), "title": (sheet or {}).get("title")},
        "rule": rule,
        "totals": {"payloads": len(rows), "recipients": len(by_recipient),
                   "carried": len(carried), "carried_to_stores": sum(1 for r in carried if r.get("kind") == "store"),
                   "undeclared": sum(1 for r in rows if any(h.partition(": ")[0] not in (r.get("declared_classes") or [])
                                                            for h in r.get("sealed_found_in_payload") or [])),
                   "blocked": sum(1 for r in rows if r.get("blocked")),
                   "messages": len(messages), "messages_stopped": sum(1 for m in messages if m.get("removed")),
                   "messages_refused": sum(1 for m in messages if not m.get("sent")),
                   "spans_stopped": sum(len(m.get("removed") or []) for m in messages),
                   "from": times[0] if times else None, "to": times[-1] if times else None},
        "rows": out_rows, "columns": columns, "cells": cells,
    }


def collect() -> dict:
    """The matrix for the sheet on the table, from the live records. Never raises: a source that fails is named."""
    src, missing = {}, []

    def read(name, fn, default):
        try:
            return fn()
        except Exception as error:  # noqa: BLE001
            missing.append({"id": name, "note": type(error).__name__})
            return default

    def _sheet():
        from signoff.engine import state
        return state.get_state()

    def _rows():
        from signoff.obs.egress import rows
        return rows()

    def _talk():
        from signoff.talk import api
        return api.threads()

    state = read("state", _sheet, {}) or {}
    talk = read("talk", _talk, {}) or {}
    from signoff.trail import feed
    flow = read("flow", lambda: feed.build(feed.collect()).get("flow"), None)
    out = build(state.get("sheet") or {}, flow, read("ledger", _rows, []), talk.get("messages") or [],
                talk.get("rule") or {}, talk.get("marks") or {})
    out["missing"] = missing
    return out
