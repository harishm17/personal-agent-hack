"""The run as one ordered feed, merged from records that already exist. Read-only: nothing here changes the app.

`collect()` reads every source in-process (each one guarded: a source that fails is an empty list and is named in
`sources`). `build(src)` is a pure function over what was collected, so tests feed it plain dicts.

An event exists only if a record does. Records of the same kind, between the same two lanes, about the same party,
that follow each other within GAP_S seconds are one event with a `count` (37 pages from one store are one mark, not
37); `duration_ms` is then the time from the first to the last of them. A record with its own measured duration
keeps it. Where no timing was recorded, `duration_ms` is null.
"""
import datetime
import re

GAP_S = 90          # records of one kind closer together than this are one event
ITEMS = 30          # at most this many records are listed inside one event; the rest are counted in `more`

# Lane ids, left to right as the view stacks them. Labels are filled from the active sheet in `lanes()`.
LANE_IDS = ("approver", "shopper", "stores", "reader", "agent", "checks", "records")
# Services whose answer is a verdict on a person or a sentence. Every other service keeps or measures records.
CHECKERS = {"senso", "persona"}

# Where a receipt is drawn: (lane, to_lane, kind). A type not listed is still a receipt on the agent's lane.
RECEIPT_PLACE = {
    "chain_started": ("records", "records", "receipt"),
    "request_accepted": ("approver", "agent", "request"),
    "request_refused": ("approver", "agent", "request"),
    "limit_set": ("agent", "agent", "limit"),
    "strike": ("agent", "agent", "strike"),
    "unstrike": ("agent", "agent", "strike"),
    "shopper_fact": ("shopper", "agent", "measurement"),
    "signed": ("agent", "agent", "signature"),
    "carts_created": ("agent", "stores", "cart"),
    "carts_updated": ("agent", "stores", "cart"),
    "reader_switched": ("agent", "reader", "reader"),
}
# What a signed request carried, by its own `type`.
REQUEST_KIND = {"set_limit": "limit", "strike": "strike", "unstrike": "strike", "sign_sheet": "signature"}

# The waterfall: which events count towards which step.
STEPS = (
    ("search", "Search", lambda e: e["kind"] == "page"),
    ("read", "Read", lambda e: e["to_lane"] == "reader" and e["kind"] == "message"),
    ("check", "Check", lambda e: e["lane"] == "checks"),
    ("ask", "Ask", lambda e: e["kind"] == "answer"),
    ("sign", "Sign", lambda e: e["lane"] == "approver" and e["source"] == "receipt"),
    ("cart", "Cart", lambda e: e["kind"] == "cart" and e["lane"] == "stores"),
)


def _plain(s) -> str:
    return str(s if s is not None else "").replace("_", " ").strip()


def _epoch(at, naive=datetime.timezone.utc):
    """Seconds since the epoch for an ISO time or a number; None when it cannot be read. A time written without
    a zone is taken as `naive` (the services that write such times write UTC)."""
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        return float(at) / (1000.0 if at > 1e11 else 1.0)
    if not isinstance(at, str) or not at.strip():
        return None
    try:
        d = datetime.datetime.fromisoformat(at.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=naive)
    return d.timestamp()


def _iso(t) -> str:
    return datetime.datetime.fromtimestamp(t).astimezone().isoformat(timespec="milliseconds")


def _iso_duration_ms(text):
    """'PT1M31S' -> 91000. None when it is not an ISO 8601 duration."""
    m = re.fullmatch(r"PT(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?", str(text or ""))
    if not m or not any(m.groups()):
        return None
    h, mi, s = (float(g) if g else 0.0 for g in m.groups())
    return int(round((h * 3600 + mi * 60 + s) * 1000))


def _money(cents) -> str:
    return "$%.2f" % (cents / 100.0) if isinstance(cents, (int, float)) and not isinstance(cents, bool) else ""


def _scalars(detail) -> str:
    """A receipt's small detail as words: its scalar fields in the order they were written; long hashes cut."""
    if not isinstance(detail, dict):
        return ""
    parts = []
    for k, v in detail.items():
        if isinstance(v, bool) or not isinstance(v, (str, int, float)):
            continue
        if isinstance(v, str) and len(v) > 16 and re.fullmatch(r"[0-9a-f]+", v):
            v = v[:8]
        parts.append("%s %s" % (_plain(k), v))
    return " · ".join(parts)


def lanes(state: dict) -> list:
    sheet = (state or {}).get("sheet") or {}
    issuer, shopper = sheet.get("issuer") or {}, sheet.get("shopper") or {}
    stores = sheet.get("stores") or []
    reader = ((state or {}).get("readers") or {}).get("reference") or ""
    named = {
        "approver": (issuer.get("name") or "Approver", issuer.get("role_label") or ""),
        "shopper": (shopper.get("name") or "Shopper", shopper.get("role_label") or ""),
        "stores": ("Stores", "%d" % len(stores) if stores else ""),
        "reader": ("Reading model", reader.split(":")[-1]),
        "agent": ("Agent", ""),
        "checks": ("Checks", ""),
        "records": ("Records", ""),
    }
    return [{"id": i, "label": named[i][0], "sub": named[i][1]} for i in LANE_IDS]


def _lane_of(row: dict) -> str:
    kind = row.get("kind")
    if kind == "store":
        return "stores"
    if kind == "model":
        return "reader"
    return "checks" if str(row.get("recipient") or "").split(":")[0].lower() in CHECKERS else "records"


def _atoms(src: dict) -> list:
    """One atom per record that carries a time."""
    out = []

    def add(at, lane, to_lane, kind, one, many, **more):
        t = _epoch(at)
        if t is None:
            return
        out.append({"t": t, "lane": lane, "to_lane": to_lane, "kind": kind, "one": one, "many": many,
                    "detail": "", "ref": None, "duration_ms": None, "verified": None, "stopped": False,
                    "facts": [], "source": "", "group": None, "units": 1, "item": {}, **more})

    state = src.get("state") or {}

    # the order document, as the agent read it
    o = state.get("order") or {}
    if o.get("derived_at"):
        n, match = o.get("limits_derived"), o.get("limits_matching")
        add(o["derived_at"], "approver", "agent", "order", "limit read", "limits read", units=n or 1,
            detail=o.get("reading") or "", ref=o.get("doc"), source="order", facts=["order"],
            verified=(n == match) if isinstance(n, int) and isinstance(match, int) else None,
            item={"title": o.get("title") or "", "quote": o.get("reading") or "", "by": o.get("extractor") or ""})

    # what came back from the stores: pages, answers
    pages, answers = {}, {}
    for line in state.get("lines") or []:
        for c in line.get("candidates") or []:
            p = c.get("product") or {}
            if p.get("fetched_at"):
                pages.setdefault((p.get("store"), p.get("product_id")), p)
            for a in c.get("asked") or []:
                if a.get("asked_at"):
                    answers.setdefault((p.get("store"), a.get("asked_at"), a.get("question")), (p, a))
    for (store, _), p in pages.items():
        add(p["fetched_at"], "stores", "agent", "page", "page", "pages", detail=store or "", source="pool",
            facts=["store_text"], group=("page", store),
            item={"title": p.get("title") or "", "link": p.get("url"), "price": _money(p.get("price_cents"))})
    for (store, _, _), (p, a) in answers.items():
        found = bool(a.get("answered")) and a.get("start") is not None
        add(a["asked_at"], "stores", "agent", "answer", "answer", "answers", detail=store or "", source="asked",
            facts=["store_text"], group=("answer", store), verified=True if found else None,
            item={"title": a.get("question") or "", "quote": a.get("quote") or a.get("reply") or "",
                  "stated": found, "about": p.get("title") or ""})
    for a in state.get("store_answers") or []:
        if a.get("asked_at"):
            add(a["asked_at"], "stores", "agent", "answer", "answer", "answers", detail=a.get("store") or "",
                source="store_answers", facts=["store_text"], group=("answer", a.get("store")),
                item={"title": a.get("question") or "", "quote": a.get("answer") or ""})

    # everything that left the process
    for r in src.get("egress") or []:
        lane = _lane_of(r)
        facts = [c for c in r.get("fact_classes") or [] if c != "none"]
        hits = r.get("sealed_hits") or []
        add(r.get("at"), "agent", lane, "message", "message", "messages", source="ledger", facts=facts,
            detail="%s · %s" % (r.get("recipient") or "", r.get("purpose") or ""), ref="ledger %s" % r.get("n"),
            group=("message", r.get("recipient"), r.get("purpose"), bool(r.get("blocked"))),
            stopped=bool(r.get("blocked")), verified=(not hits) if lane == "stores" else None,
            item={"title": r.get("purpose") or "", "hash": r.get("payload_sha256"), "bytes": r.get("bytes"),
                  "ledger": r.get("n"), "facts": facts, "found": r.get("sealed_found_in_payload") or []})

    # the receipt chain
    chain = src.get("receipts") or []
    bad = (src.get("receipt_check") or {}).get("first_bad")
    for r in chain:
        d = r.get("detail") if isinstance(r.get("detail"), dict) else {}
        lane, to_lane, kind = RECEIPT_PLACE.get(r.get("type"), ("agent", "agent", "receipt"))
        refused = r.get("type") == "request_refused"
        words = _plain(r.get("type"))
        if kind == "request":
            kind = REQUEST_KIND.get(d.get("request"), "request")
            words = "%s %s" % (_plain(d.get("request")) or "request", "refused" if refused else "accepted")
        carts = d.get("carts") if isinstance(d.get("carts"), list) else None
        add(r.get("at"), lane, to_lane, kind, words.capitalize(), "", source="receipt",
            units=len(carts) if carts else 1, stopped=refused, ref="receipt %s" % r.get("n"),
            detail=str(d.get("refused_because") or _scalars(d)),
            verified=(bad is None or r.get("n", 0) < bad) if src.get("receipt_check") else None,
            item={"title": words, "receipt": r.get("n"), "hash": r.get("hash"), "prev_hash": r.get("prev_hash"),
                  "body_hash": r.get("body_hash"), "actor": r.get("actor"), "key_id": r.get("key_id")})

    # the reader gate's changes
    for h in (src.get("gate") or {}).get("history") or []:
        add(h.get("at"), "records", "agent", "gate", "Reader gate %s" % ("on" if h.get("value") else "off"), "",
            detail=_plain(h.get("arm")), source="gate", item={"title": "reader: %s" % _plain(h.get("arm"))})

    # Senso's verdicts on the sheet's sentences
    s = src.get("senso") or {}
    checks = s.get("checks") or []
    if s.get("ran_at") and checks:
        ok = sum(1 for c in checks if c.get("verdict") == "verified")
        add(s["ran_at"], "checks", "agent", "check", "verdict", "verdicts", units=len(checks), source="senso",
            detail="Senso · %d of %d verified" % (ok, len(checks)), verified=not s.get("blocking"),
            ref=("hash %s" % s["for_hash"][:8]) if s.get("for_hash") else None, facts=["order"],
            items=[{"title": c.get("sentence") or "", "quote": c.get("quote") or "", "verdict": c.get("verdict"),
                    "run": c.get("run_id")} for c in checks])

    # the signer's checks: who (Persona Inquiry) and that a person tapped (Relay)
    p = src.get("persona") or {}
    for key in ("checked_at", "completed_at", "at", "created_at"):
        if p.get("inquiry_id") and p.get(key):
            add(p[key], "checks", "agent", "identity", "Identity check", "", detail=p.get("label") or "",
                ref=p.get("inquiry_id"), source="persona", verified=bool(p.get("verified")),
                item={"title": p.get("label") or "", "status": p.get("status")})
            break
    rl = src.get("relay") or {}
    if rl.get("at"):
        add(rl["at"], "checks", "agent", "identity", _plain(rl.get("claim_type")).capitalize() or "Relay claim", "",
            detail="%s%s" % (_plain(rl.get("result")), " · sandbox" if rl.get("sandbox") else ""), source="relay",
            verified=True if rl.get("result") in ("pass", "passed", True) else None,
            item={"title": _plain(rl.get("claim_type")), "status": rl.get("result")})

    # Airbyte's jobs
    last = (src.get("airbyte") or {}).get("last") or {}
    for j in last.get("jobs") or []:
        rows = j.get("rows_synced")
        add(last.get("finished_at"), "records", "agent", "sync", "row synced", "rows synced",
            units=rows if isinstance(rows, int) and rows > 0 else 1, source="airbyte",
            detail="Airbyte · %s" % _plain(j.get("stream")), ref="airbyte job %s" % j.get("job_id"),
            duration_ms=_iso_duration_ms(j.get("duration")), stopped=j.get("status") != "succeeded",
            item={"title": _plain(j.get("stream")), "status": j.get("status"),
                  "copied": j.get("rows_copied_to_singlestore")})

    # carts, as the stores returned them
    for c in (state.get("seal") or {}).get("carts") or []:
        if c.get("created_at"):
            made = bool(c.get("cart_url"))
            add(c["created_at"], "stores", "agent", "cart", "Cart created" if made else "Cart pending", "",
                detail=" · ".join(x for x in (c.get("store") or "", _money(c.get("total_cents")), c.get("mode") or "") if x),
                ref=c.get("cart_id"), source="cart", facts=["price"],
                item={"title": c.get("store") or "", "link": c.get("cart_url"), "price": _money(c.get("total_cents"))})
    return out


def _events(atoms: list) -> list:
    """Atoms in time order; those that share a `group` and follow each other within GAP_S become one event."""
    atoms = sorted(atoms, key=lambda a: a["t"])
    open_groups, events = {}, []
    for a in atoms:
        items = a.pop("items", None) or [a["item"]]
        g = open_groups.get(a["group"]) if a["group"] else None
        if g is not None and a["t"] - g["_last"] <= GAP_S:
            g["count"] += a["units"]
            g["_last"] = a["t"]
            g["_items"].extend(items)
            g["_verified"].append(a["verified"])
            continue
        e = {"t": a["t"], "lane": a["lane"], "to_lane": a["to_lane"], "kind": a["kind"], "detail": a["detail"],
             "ref": a["ref"], "duration_ms": a["duration_ms"], "count": a["units"], "stopped": a["stopped"],
             "facts": a["facts"], "source": a["source"], "_one": a["one"], "_many": a["many"], "_last": a["t"],
             "_items": list(items), "_verified": [a["verified"]]}
        events.append(e)
        if a["group"]:
            open_groups[a["group"]] = e
    out = []
    for n, e in enumerate(events, 1):
        seen = e.pop("_verified")
        items, one, many, last = e.pop("_items"), e.pop("_one"), e.pop("_many"), e.pop("_last")
        if e["duration_ms"] is None and last > e["t"]:
            e["duration_ms"] = int(round((last - e["t"]) * 1000))
        label = ("%d %s" % (e["count"], many if e["count"] != 1 else one)) if many else one
        out.append({"n": n, "at": _iso(e["t"]), "end_at": _iso(last) if last > e["t"] else None,
                    "t": int(e["t"] * 1000), "lane": e["lane"], "to_lane": e["to_lane"], "kind": e["kind"],
                    "label": label, "detail": e["detail"][:200], "ref": e["ref"], "duration_ms": e["duration_ms"],
                    "count": e["count"],
                    "verified": False if False in seen else (True if seen and all(v is True for v in seen) else None),
                    "verified_count": sum(1 for v in seen if v is True) if any(v is not None for v in seen) else None,
                    "stopped": e["stopped"], "facts": e["facts"], "source": e["source"],
                    "items": items[:ITEMS], "more": max(0, len(items) - ITEMS)})
    return out


def _steps(events: list) -> list:
    out = []
    for step_id, label, belongs in STEPS:
        mine = [e for e in events if belongs(e)]
        timed = [e["duration_ms"] for e in mine if e["duration_ms"] is not None]
        out.append({"id": step_id, "label": label, "events": len(mine), "count": sum(e["count"] for e in mine),
                    "duration_ms": sum(timed) if timed else None,
                    "first_at": mine[0]["at"] if mine else None, "last_at": mine[-1]["at"] if mine else None})
    return out


def build(src: dict) -> dict:
    """The feed. `src` is what `collect()` returns; every key may be missing."""
    src = src or {}
    state = src.get("state") or {}
    events = _events(_atoms(src))
    chain = src.get("receipts") or []
    check = src.get("receipt_check") or {}
    bad = check.get("first_bad")
    held = len(chain) if check.get("verified") else (max(0, bad - 1) if isinstance(bad, int) else 0)
    eg = src.get("egress_summary") or {}
    sheet = state.get("sheet") or {}
    return {
        "sheet": {"id": sheet.get("id"), "title": sheet.get("title"), "invented": sheet.get("invented"),
                  "items": len(state.get("lines") or [])},
        "mode": state.get("mode"),
        "state_version": state.get("version"),
        "signed": bool((state.get("seal") or {}).get("signed")),
        "lanes": lanes(state),
        "events": events,
        "chain": [{"n": r.get("n"), "at": r.get("at"), "type": r.get("type"), "hash": r.get("hash"),
                   "prev_hash": r.get("prev_hash"), "verified": bool(check) and (bad is None or r.get("n", 0) < bad)}
                  for r in chain],
        "summary": {"events": len(events), "records": sum(len(e["items"]) + e["more"] for e in events),
                    "messages_out": eg.get("messages"), "to_stores": eg.get("to_stores"),
                    "limits_to_stores": eg.get("limits_in_store_messages"), "blocked": eg.get("blocked"),
                    "receipts": len(chain), "receipts_verified": held},
        "steps": _steps(events),
        "sources": src.get("sources") or [],
    }


def collect() -> dict:
    """Every source, read in-process. Never raises: a source that fails is left out and named in `sources`."""
    src, sources = {}, []

    def read(name, fn):
        try:
            value = fn()
            sources.append({"id": name, "ok": True})
            return value
        except Exception as error:  # noqa: BLE001
            sources.append({"id": name, "ok": False, "note": type(error).__name__})
            return None

    def _state():
        from signoff.engine import state
        return state.get_state()

    def _receipts():
        from signoff.engine import receipts
        held = receipts.chain()["receipts"]
        src["receipt_check"] = receipts.check(held)
        return held

    def _egress():
        from signoff.obs import egress as ledger_module  # noqa: F401  (the package attribute is the function)
        from signoff.obs.egress import rows, summary
        rs = rows()
        src["egress_summary"] = summary(rs)
        return rs

    def _gate():
        from signoff.obs import gate
        return {"history": list(gate._s.get("history") or [])}

    def _senso():
        from signoff.sign import senso
        return senso.checks()

    def _persona():
        from signoff.sign import persona
        return persona.record()

    def _relay():
        from signoff.relay import core
        return core.status()

    def _airbyte():
        from signoff.airbyte import api
        return api.status()

    for name, fn in (("state", _state), ("receipts", _receipts), ("egress", _egress), ("gate", _gate),
                     ("senso", _senso), ("persona", _persona), ("relay", _relay), ("airbyte", _airbyte)):
        src[name] = read(name, fn)
    src["sources"] = sources
    return src
