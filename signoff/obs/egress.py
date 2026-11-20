"""The outbound ledger: one row for everything that leaves this process (stores, model providers, sponsor services).

`record(recipient, purpose, payload, fact_classes=None)` never raises and never blocks. A row keeps who, why, how many
bytes, the payload's SHA-256 and the fact classes it carries; never the payload itself. The guard is code, not a model:
it looks in the serialised payload for the sheet's sealed values (an issuer limit value with its unit, a shopper
measurement with its unit, a person's name). For a payload to a store any such hit is listed in `sealed_hits`, and the
store client refuses to send it. Rows are kept in memory and appended to data/egress/ledger.jsonl.

Import note: `signoff.obs.egress` is the function (`obs.egress(...)`); this module is reached as
`from signoff.obs.egress import record, rows, summary`.
"""
import datetime
import hashlib
import json
import pathlib
import re
import threading

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LEDGER = ROOT / "data" / "egress" / "ledger.jsonl"
CLASSES = {"limit", "home_measurement", "person", "order", "store_text", "product", "price", "none"}
MODELS = {"anthropic", "sie", "arcee", "openai", "claude"}
UNITS = {"lb": r"(?:lbs?\.?|pounds?)", "in": r"(?:in\b\.?|inch(?:es)?\b|\"|”|″)"}
_lock = threading.Lock()
_rows: list = []
_loaded = False


def _sheet_values() -> dict:
    """Sealed values of the sheet the engine runs now (its limits may have moved) and of the sheet on disk."""
    limits, facts, people, stores = set(), set(), set(), set()
    sheets = []
    try:
        from signoff.engine import state as engine
        s = getattr(engine, "_s", {}).get("sheet")  # no lock taken: egress may be called from inside the engine
        if s:
            sheets.append(s)
    except Exception:  # noqa: BLE001
        pass
    try:
        sheets.append(json.loads((ROOT / "sheets" / "sheet1.json").read_text()))
    except Exception:  # noqa: BLE001
        pass
    for sh in sheets:
        stores.update(sh.get("stores", []))
        for who in ("issuer", "shopper"):
            if sh.get(who, {}).get("name"):
                people.add(sh[who]["name"])
        for f in sh.get("shopper_facts", []):
            facts.add((float(f["value"]), f.get("unit", "")))
        for line in sh.get("lines", []):
            for lim in line.get("limits", []):
                b = lim.get("bound", {})
                if b.get("source") == "issuer":
                    limits.add((float(b["value"]), lim.get("unit", "")))
    return {"limits": limits, "facts": facts, "people": people, "stores": stores}


def _num_pattern(v: float) -> str:
    whole = int(v) if float(v).is_integer() else None
    return (rf"{whole}(?:\.0+)?" if whole is not None else re.escape(repr(v))).join(["(?<![\\d.])", "(?!\\d)"])


def detect(text: str, sealed: dict | None = None) -> list[dict]:
    """Sealed values found in `text`: [{"class": limit|home_measurement|person, "match": "300 lb"}]."""
    sealed = sealed or _sheet_values()
    hits = []

    def scan(pairs, cls):
        for v, unit in pairs:
            u = UNITS.get(unit)
            if not u:
                continue
            for m in re.finditer(_num_pattern(v) + r"\s*-?\s*" + u, text, re.I):
                hits.append({"class": cls, "match": m.group(0).strip().rstrip(".")})

    scan(sealed["limits"], "limit")
    scan(sealed["facts"], "home_measurement")
    for name in sealed["people"]:
        for m in re.finditer(rf"\b{re.escape(name)}\b", text):
            hits.append({"class": "person", "match": m.group(0)})
    seen, out = set(), []
    for h in hits:
        k = (h["class"], h["match"].lower())
        if k not in seen:
            seen.add(k)
            out.append(h)
    return out


def kind_of(recipient: str, sealed: dict | None = None) -> str:
    r = recipient.lower()
    if r.split(":")[0] in MODELS:
        return "model"
    if (sealed or _sheet_values())["stores"] & {recipient} or re.search(r"\.(com|co|net|org)$", r):
        return "store"
    return "sponsor service"


def _load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        if LEDGER.exists():
            _rows.extend(json.loads(l) for l in LEDGER.read_text().splitlines() if l.strip())
    except Exception:  # noqa: BLE001
        pass


def record(recipient: str, purpose: str, payload=None, fact_classes=None, kind: str | None = None,
           block_on_hit: bool = False) -> dict:
    """Add one row and return it (`sealed_hits` empty means clean). Never raises. With block_on_hit, a store payload with a
    sealed value is marked `blocked: true` and the caller must not send it."""
    try:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
        raw = text.encode()
        sealed = _sheet_values()
        k = kind or kind_of(recipient, sealed)
        found = detect(text, sealed)
        declared = sorted(c for c in (fact_classes or []) if c in CLASSES)
        classes = sorted(set(declared) | {h["class"] for h in found}) or ["none"]
        row = {"at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "recipient": recipient,
               "kind": k, "purpose": purpose, "bytes": len(raw), "payload_sha256": hashlib.sha256(raw).hexdigest(),
               "fact_classes": classes, "declared_classes": declared or ["none"],
               "sealed_hits": found if k == "store" else [],
               "sealed_found_in_payload": [h["class"] + ": " + h["match"] for h in found]}
        if block_on_hit and row["sealed_hits"]:
            row["blocked"] = True
        with _lock:
            _load()
            row["n"] = (_rows[-1]["n"] + 1) if _rows else 1
            _rows.append(row)
            del _rows[:-5000]
            try:
                LEDGER.parent.mkdir(parents=True, exist_ok=True)
                with LEDGER.open("a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
            except Exception:  # noqa: BLE001
                pass
        return row
    except Exception:  # noqa: BLE001
        return {"sealed_hits": [], "error": True}


def rows() -> list[dict]:
    with _lock:
        _load()
        return [dict(r) for r in _rows]


def summary(rs: list[dict] | None = None) -> dict:
    rs = rs if rs is not None else rows()
    to_stores = [r for r in rs if r["kind"] == "store"]

    def n(cls):
        return sum(1 for r in to_stores if any(h["class"] == cls for h in r["sealed_hits"]))

    by: dict = {}
    for r in rs:
        by[r["recipient"]] = by.get(r["recipient"], 0) + 1
    return {"messages": len(rs), "by_recipient": dict(sorted(by.items(), key=lambda kv: -kv[1])),
            "by_kind": {k: sum(1 for r in rs if r["kind"] == k) for k in ("store", "model", "sponsor service")},
            "to_stores": len(to_stores), "limits_in_store_messages": n("limit"),
            "home_measurements_in_store_messages": n("home_measurement"), "people_in_store_messages": n("person"),
            "blocked": sum(1 for r in rs if r.get("blocked")),
            "checked_by": "code: sealed limit and home values with their units and the sheet's names, searched in the serialised payload"}


def reset_for_tests() -> None:
    global _loaded
    with _lock:
        _rows.clear()
        _loaded = True
