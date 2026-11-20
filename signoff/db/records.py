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
                         _unit(lim.get("unit")), lim.get("several"), state["version"]))
    return rows


def _pool_fingerprint(pool: list) -> str:
    return hashlib.sha256(json.dumps(pool, sort_keys=True).encode()).hexdigest()[:16]


def _bulk(cur, head: str, rows: list, chunk: int = 100) -> None:
    """One multi-row INSERT per chunk: the database is remote, so round trips dominate."""
    for i in range(0, len(rows), chunk):
        part = rows[i:i + chunk]
        ph = "(" + ",".join(["%s"] * len(part[0])) + ")"
        cur.execute(head + " VALUES " + ",".join([ph] * len(part)), [v for r in part for v in r])


def _figure_rows(state: dict) -> tuple[list, list]:
    """(pool rows, figure rows): one pool row per candidate; one figure row per statement the engine holds for the candidate,
    plus one single-value row for each other number the engine says the quote may state (`possible`)."""
    pool_rows, fig_rows = [], []
    for line in state["lines"]:
        for cand in line["candidates"]:
            pr = cand["product"]
            pool_rows.append((cand["id"], line["line_id"], pr["store"], pr["product_id"], pr.get("variant_id"), pr["title"],
                              pr["price_cents"], pr["product_key"], pr.get("url")))
            seen: dict = {}
            for f in cand["figures"]:
                idx = seen[f["figure"]] = seen.get(f["figure"], -1) + 1
                fig_rows.append((cand["id"], f["figure"], idx, f["kind"], f.get("value"), f.get("low"), f.get("high"),
                                 _unit(f.get("unit")), f.get("quote"), f.get("start"), f.get("end"), f.get("extractor"),
                                 1 if f.get("span_found_in_text") else 0, 1 if f.get("unsure") else 0,
                                 None if f.get("number_in_quote") is None else (1 if f.get("number_in_quote") else 0),
                                 f.get("for_other_option")))
                for other in f.get("possible") or []:
                    if isinstance(other, (int, float)) and not isinstance(other, bool):
                        idx = seen[f["figure"]] = seen[f["figure"]] + 1
                        fig_rows.append((cand["id"], f["figure"], idx, "single", other, other, other, _unit(f.get("unit")),
                                         f.get("quote"), f.get("start"), f.get("end"), f.get("extractor"),
                                         1 if f.get("span_found_in_text") else 0, 1 if f.get("unsure") else 0,
                                         None if f.get("number_in_quote") is None else (1 if f.get("number_in_quote") else 0),
                                         f.get("for_other_option")))
    return pool_rows, fig_rows


_write_lock = threading.Lock()


def _write_now(state: dict) -> None:
    """One writer at a time in this process (the background worker and a request must not interleave)."""
    with _write_lock:
        _write_now_locked(state)


def _write_now_locked(state: dict) -> None:
    _learn_units(state)
    schema.ensure()
    c = conn.connect()
    try:
        cur = c.cursor()
        pool_rows, fig_rows = _figure_rows(state)
        decisions, strikes = [], {}
        for line in state["lines"]:
            for st in line.get("struck", []):
                strikes[(line["line_id"], st["product_key"])] = st.get("reason")
            for cand in line["candidates"]:
                pr = cand["product"]
                decisions.append((state["version"], cand["id"], line["line_id"], pr["store"], pr["product_id"],
                                  pr["product_key"], cand["status"], cand.get("reason"), 1 if cand.get("picked") else 0,
                                  pr["price_cents"], json.dumps(cand)))
        from signoff import obs  # the ledger: this write leaves the process for SingleStore
        obs.egress("singlestore", "write candidates, figures, limits, strikes and decision records", {
            "pool": pool_rows, "figures": fig_rows, "limits": limit_rows(state), "strikes": list(strikes.items()),
            "decisions": decisions}, ["limit", "home_measurement", "store_text", "product", "price", "order"])
        cur.execute("DELETE FROM pool")
        _bulk(cur, "INSERT INTO pool (cand_id, line_id, store, product_id, variant_id, title, price_cents, product_key, url)", pool_rows)
        cur.execute("DELETE FROM figures")
        _bulk(cur, "INSERT INTO figures (cand_id, figure, idx, kind, value, low, high, unit, quote, start_pos, end_pos,"
                   " extractor, span_found_in_text, unsure, number_in_quote, for_other_option)", fig_rows)
        cur.execute("DELETE FROM limits")
        _bulk(cur, "INSERT INTO limits (limit_id, line_id, name, op, figure, shopper_sum, bound, unit, several, state_version)",
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
