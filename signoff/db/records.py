"""Writes the pool, the figures, the limits, the strikes and the decision records to SingleStore.

`write(state)` never raises and never blocks the caller: the newest state is handed to one worker thread
(older states waiting are dropped; the app works with the database down).
"""
import hashlib
import json
import logging
import threading

from signoff.db import conn, schema

log = logging.getLogger("signoff.db")
_lock = threading.Lock()
_pending: dict | None = None
_wake = threading.Event()
_worker: threading.Thread | None = None
_last_error: str | None = None


def last_error() -> str | None:
    return _last_error


def _shopper_values(state: dict) -> dict:
    return {f["id"]: f["value"] for f in state["sheet"].get("shopper_facts", [])}


_sheet_units: dict = {}  # alias (lower case) -> the sheet's own unit name, set from the state being written


def _unit(u):
    """One name for a unit: the sheet's own spellings (its `units` block: "count" is ct, pack, crayons...) first, then the
    engine's alias table ("inch" is "in"), else the unit as written."""
    key = str(u or "").strip().lower()
    if key in _sheet_units:
        return _sheet_units[key]
    try:
        from signoff.engine import rules
        return rules.unit_name(u) or u
    except Exception:  # noqa: BLE001
        return u


def _learn_units(state: dict) -> None:
    _sheet_units.clear()
    for canonical, aliases in ((state.get("sheet") or {}).get("units") or {}).items():
        _sheet_units[str(canonical).lower()] = canonical
        for a in aliases:
            _sheet_units[str(a).strip().lower()] = canonical


def limit_rows(state: dict) -> list[tuple]:
    _learn_units(state)
    facts, rows = _shopper_values(state), []
    for line in state["sheet"]["lines"]:
        for lim in line["limits"]:
            shopper = sum(facts[t["fact"]] for t in lim["terms"] if t["source"] == "shopper")
            store = [t["figure"] for t in lim["terms"] if t["source"] == "store"]
            b = lim["bound"]
            bound = b["value"] if b["source"] == "issuer" else facts[b["fact"]]
            rows.append((lim["id"], line["id"], lim["name"], lim["op"], store[0] if store else None, shopper, bound,
                         _unit(lim.get("unit")), state["version"]))
    return rows


def _pool_fingerprint(pool: list) -> str:
    return hashlib.sha256(json.dumps(pool, sort_keys=True).encode()).hexdigest()[:16]


def _bulk(cur, head: str, rows: list, chunk: int = 100) -> None:
    """One multi-row INSERT per chunk: the database is remote, so round trips dominate."""
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        ph = "(" + ",".join(["%s"] * len(part[0])) + ")"
        cur.execute(head + " VALUES " + ",".join([ph] * len(part)), [v for r in part for v in r])


def sync_pool(cur, pool: list) -> None:
    cur.execute("SELECT v FROM meta WHERE k = 'pool_fp'")
    row = cur.fetchone()
    fp = _pool_fingerprint(pool)
    if row and row[0] == fp:
        return
    cur.execute("DELETE FROM pool")
    _bulk(cur, "INSERT INTO pool (store, product_id, variant_id, title, price_cents, url, text, fetched_at, product_key, line_ids)",
          [(p["store"], p["product_id"], p["variant_id"], p["title"], p["price_cents"], p["url"], p["text"],
          p["fetched_at"], p["product_key"], json.dumps(p["line_ids"])) for p in pool])
    cur.execute("REPLACE INTO meta (k, v) VALUES ('pool_fp', %s)", (fp,))


_write_lock = threading.Lock()


def _write_now(state: dict) -> None:
    """One writer at a time in this process (the background worker and a request must not interleave)."""
    with _write_lock:
        _write_now_locked(state)


def _write_now_locked(state: dict) -> None:
    _learn_units(state)
    schema.ensure()
    from signoff.store import pool as pool_mod
    c = conn.connect()
    try:
        cur = c.cursor()
        sync_pool(cur, pool_mod.load()[0])
        figs, decisions, strikes = {}, [], {}
        for line in state["lines"]:
            for s in line.get("struck", []):
                strikes[(line["line_id"], s["product_key"])] = s.get("reason")
            for cand in line["candidates"]:
                for f in cand["figures"]:
                    key = (f["store"], f["product_id"], f["figure"])
                    rank = (0 if f.get("span_found_in_text") else 2) + (1 if f.get("unsure") else 0)
                    if key in figs and figs[key][0] <= rank:  # the engine keeps the first usable figure per name
                        continue
                    figs[key] = (rank, (
                        f["store"], f["product_id"], f["figure"], f["kind"], f.get("value"), f.get("low"), f.get("high"),
                        _unit(f.get("unit")), f.get("quote"), f.get("start"), f.get("end"), f.get("extractor"),
                        1 if f.get("span_found_in_text") else 0, 1 if f.get("unsure") else 0))
                pr = cand["product"]
                decisions.append((state["version"], cand["id"], line["line_id"], pr["store"], pr["product_id"],
                                  pr["product_key"], cand["status"], cand.get("reason"), 1 if cand.get("picked") else 0,
                                  pr["price_cents"], json.dumps(cand)))
        from signoff import obs  # the ledger: this write leaves the process for SingleStore
        obs.egress("singlestore", "write pool, figures, limits, strikes and decision records", {
            "figures": [v[1] for v in figs.values()], "limits": limit_rows(state), "strikes": list(strikes.items()),
            "decisions": decisions}, ["limit", "home_measurement", "store_text", "product", "price", "order"])
        cur.execute("DELETE FROM figures")
        _bulk(cur, "INSERT INTO figures (store, product_id, figure, kind, value, low, high, unit, quote,"
                   " start_pos, end_pos, extractor, span_found_in_text, unsure)", [v[1] for v in figs.values()])
        cur.execute("DELETE FROM limits")
        _bulk(cur, "INSERT INTO limits (limit_id, line_id, name, op, figure, shopper_sum, bound, unit, state_version)",
              limit_rows(state))
        cur.execute("DELETE FROM strikes")
        _bulk(cur, "INSERT INTO strikes (line_id, product_key, reason)", [(k[0], k[1], v) for k, v in strikes.items()])
        _bulk(cur, "REPLACE INTO decisions (state_version, candidate_id, line_id, store, product_id, product_key,"
                   " status, reason, picked, price_cents, record)", decisions)
    finally:
        c.close()


def _loop() -> None:
    global _pending, _last_error
    while True:
        _wake.wait()
        _wake.clear()
        with _lock:
            state, _pending = _pending, None
        if state is None:
            continue
        try:
            _write_now(state)
            _last_error = None
        except Exception as e:  # noqa: BLE001
            _last_error = type(e).__name__ + ": " + str(e)[:160]
            log.warning("records.write failed: %s", _last_error)


def write(state: dict) -> None:
    """Queue this state for SingleStore. Never raises, never waits."""
    global _pending, _worker
    try:
        with _lock:
            _pending = state
            if _worker is None or not _worker.is_alive():
                _worker = threading.Thread(target=_loop, name="records-writer", daemon=True)
                _worker.start()
        _wake.set()
    except Exception:  # noqa: BLE001
        pass


def write_sync(state: dict) -> None:
    """For tests and the first load: write now, raise on failure."""
    _write_now(state)
