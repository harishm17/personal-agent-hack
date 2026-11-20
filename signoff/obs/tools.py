"""`GET /api/tools`: one row per tool that did real work in this run, each with one true number read from its owner's route or file
at request time. A tool with no real call is absent (and listed under `absent` with the reason). Nothing here is invented: every
number is a count or a status that the source returned.

Row: {tool, job (five words or fewer), number, unit, detail, source, ok, basis}. `ok` is true when a real call succeeded in this
process for this request; `basis` says plainly "live call just now", "this process since it started" or "saved run (<when>)".
"""
import asyncio
import datetime
import json
import pathlib
import re
import threading
import time

import httpx

from signoff import obs
from signoff.store import sheetctx

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
_cache: dict = {}
TTL = 20.0


async def _get(app, path: str) -> dict | None:
    """Read another stream's route in-process (no network), as the browser would."""
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 0)), base_url="http://app", timeout=60) as c:
            r = await c.get(path)
            return r.json() if r.status_code == 200 else None
    except Exception:  # noqa: BLE001
        return None


def _row(tool, job, number, unit, detail, source, ok, basis) -> dict:
    assert len(job.split()) <= 5, job
    return {"tool": tool, "job": job, "number": number, "unit": unit, "detail": detail, "source": source, "ok": bool(ok), "basis": basis}


def _line(state: dict, wanted: str | None) -> dict:
    lines = state["lines"]
    if wanted:
        for l in lines:
            if l["line_id"] == wanted:
                return l
    return next((l for l in lines if l.get("pick")), lines[0])


def _sql_parts_now(line_id: str | None) -> dict:
    """SingleStore and Airbyte: write the engine's own state to the tables, run the passing-box statement for the line, compare it
    with the engine's inside set, count the decision records; run the same statement on the rows Airbyte delivered. Blocking
    (run in a thread). The state is read in-process, not through the JSON route, so the tables hold exactly what the engine holds."""
    from signoff.db import conn, passing, records
    from signoff.engine import state as engine
    state = engine.get_state()
    line = _line(state, line_id)
    key = (state["sheet"]["id"], state["version"], line["line_id"])
    out: dict = {"line": {"line_id": line["line_id"], "need": line.get("need")}}
    try:
        records.write_sync(state)
        inside = {c["id"] for c in line["candidates"] if c["status"] == "inside"}
        try:
            ab = passing.passing_box(line["line_id"], "airbyte")  # computes the direct answer too
            direct_rows = ab["direct_rows"]
        except Exception as e:  # noqa: BLE001
            ab, direct_rows = None, passing.passing_box(line["line_id"])["rows"]
            out["airbyte_error"] = type(e).__name__
        got = {r["cand_id"] for r in direct_rows}
        c = conn.connect()
        try:
            cur = c.cursor()
            cur.execute("SELECT COUNT(*), COUNT(DISTINCT state_version) FROM decisions")
            n, versions = cur.fetchone()
            run = None
            if ab:
                cur.execute("SELECT run_id, finished_at, ok, detail FROM signoff.airbyte_runs ORDER BY finished_at DESC LIMIT 1")
                run = cur.fetchone()
        finally:
            c.close()
        out["singlestore"] = {"rows": len(got), "engine": len(inside), "same": got == inside, "decisions": n, "versions": versions}
        if ab:
            jobs = []
            if run:
                detail = run[3] if isinstance(run[3], dict) else json.loads(run[3] or "{}")
                jobs = [j.get("job_id") for j in detail.get("jobs", [])]
            out["airbyte"] = {"same": ab["same"], "rows": len(ab["rows"]), "delivered": ab["airbyte"]["rows"], "jobs": ab["airbyte"]["jobs"],
                              "last_synced_at": ab["airbyte"]["last_synced_at"], "last_run_jobs": jobs,
                              "last_run_at": str(run[1]) if run else None, "last_run_ok": bool(run[2]) if run else None}
    except Exception as e:  # noqa: BLE001
        out["singlestore_error"] = type(e).__name__
    _cache["sql"] = {"key": key, "at": time.time(), "value": out}
    return out


_refreshing = threading.Lock()


def _sql_parts(line_id: str | None) -> dict:
    """The SQL parts, cached for TTL seconds per (sheet, state version, line). A stale entry is returned at once and refreshed in
    the background, so only the very first call (about ten seconds against the remote database) waits."""
    try:
        from signoff.engine import state as engine
        st = engine.get_state()
        key = (st["sheet"]["id"], st["version"], _line(st, line_id)["line_id"])
    except Exception:  # noqa: BLE001
        return {"singlestore_error": "no engine state"}
    hit = _cache.get("sql")
    if hit and hit["key"] == key and time.time() - hit["at"] < TTL:
        return hit["value"]
    if hit and hit["value"].get("singlestore"):
        if _refreshing.acquire(blocking=False):
            def go():
                try:
                    _sql_parts_now(line_id)
                finally:
                    _refreshing.release()
            threading.Thread(target=go, name="tools-refresh", daemon=True).start()
        return {**hit["value"], "stale": True}
    return _sql_parts_now(line_id)


def prewarm(delay: float = 15.0) -> None:
    """Run the SQL parts once soon after the app starts, so the first look at the drawer does not wait for the database."""
    def go():
        time.sleep(delay)
        try:
            _sql_parts(None)
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=go, name="tools-prewarm", daemon=True).start()


def _firedrill() -> dict | None:
    """Campaign ids and per-criterion scores from evals/firedrill/*/report.txt (saved runs). A re-run after the fix exists when a
    later campaign's report carries the criterion at or above its threshold."""
    campaigns = []
    for f in sorted((ROOT / "evals" / "firedrill").glob("campaign*/report.txt"), key=lambda p: p.stat().st_mtime):
        text = f.read_text()
        m = re.match(r"Campaign ([0-9a-f-]{36})", text)
        if not m:
            continue
        scores = {}
        for crit, avg, thr, met in re.findall(r"^\s{2}(.+?)\s+average ([\d.]+) .*?threshold (\d+): (\d+) met", text, re.M):
            scores[crit.strip()] = {"average": float(avg), "threshold": int(thr), "met": int(met) > 0}
        campaigns.append({"id": m.group(1), "folder": f.parent.name, "scores": scores,
                          "saved": datetime.datetime.fromtimestamp(f.stat().st_mtime).astimezone().isoformat(timespec="minutes")})
    return {"campaigns": campaigns} if campaigns else None


async def build(app, line_id: str | None = None) -> dict:
    rows, absent = [], []
    state = await _get(app, "/api/state")
    if not state:
        return {"tools": [], "absent": [{"tool": "all", "why": "the engine's state could not be read"}], "at": time.time()}
    sheet_id = state["sheet"]["id"]
    sql = await asyncio.to_thread(_sql_parts, line_id)
    line = {**_line(state, line_id), **sql.get("line", {})}
    # SingleStore
    if "singlestore" in sql:
        s = sql["singlestore"]
        rows.append(_row("SingleStore", "Candidates inside, in SQL", s["rows"], "candidates inside the limits",
                         "One SQL statement for %s %s: %d rows, %s the engine's inside set (%d); %d decision records over %d state versions."
                         % (line["line_id"], line.get("need", ""), s["rows"], "the same as" if s["same"] else "NOT the same as", s["engine"], s["decisions"], s["versions"]),
                         "/api/sql/passing-box?line_id=%s" % line["line_id"], s["same"], "live query just now"))
    else:
        absent.append({"tool": "SingleStore", "why": sql.get("singlestore_error", "no result")})
    # Airbyte
    if "airbyte" in sql:
        a = sql["airbyte"]
        rows.append(_row("Airbyte", "Rows delivered to SingleStore", a["delivered"], "rows delivered",
                         "The same query on those rows returns %d candidates for %s: same: %s. Jobs %s, last sync %s." % (
                             a["rows"], line["line_id"], str(a["same"]).lower(), ", ".join(str(j) for j in (a["last_run_jobs"] or [])) or "n/a", a["last_synced_at"]),
                         "/api/sql/passing-box?line_id=%s&source=airbyte" % line["line_id"], a["same"],
                         "live query just now on rows delivered by saved jobs (last run %s)" % a["last_run_at"]))
    else:
        absent.append({"tool": "Airbyte", "why": sql.get("airbyte_error", "no result")})
    # Statsig
    gate = await _get(app, "/api/gate/status")
    if gate and gate.get("gate_exists_in_statsig") is not False and not gate.get("error") and gate.get("polling"):
        ev = gate.get("evidence") or {}
        rows.append(_row("Statsig", "Gate switches reading mode", ev.get("real_disagreements_caught", 0), "real disagreements caught",
                         "Gate %s is %s (%s); decision: %s. %s" % (gate["gate"], "on" if gate["value"] else "off", gate.get("deciding_reader"),
                                                                    gate.get("decision"), gate.get("decision_text") or ""),
                         "/api/gate/status", True, "live: the gate was read %ss ago" % gate.get("last_polled_ago_s")))
    else:
        absent.append({"tool": "Statsig", "why": "the gate is not being read" if gate else "no gate status"})
    # Amplitude
    st = obs.stats
    if st.get("delivered"):
        by = st.get("events_by_name") or {}
        cur = obs.current_experiments()
        seen = st.get("experiments_seen") or []
        local = obs.recent(20000)
        rows.append(_row("Amplitude", "Agent events, with the arm", st["delivered"], "events delivered",
                         "%s; variant on the session now: %s (%d distinct variant sets seen on delivered events); %d tool calls recorded in the local log."
                         % (", ".join("%d %s" % (v, k) for k, v in sorted(by.items())) or "no breakdown", ", ".join("%s=%s" % (e["key"], e["variant"]) for e in cur),
                            len(seen), len(local)),
                         "/api/obs/status", st.get("last_status") == 200, "this process since it started"))
    else:
        absent.append({"tool": "Amplitude", "why": "no event delivered in this process yet"})
    # Senso
    senso = await _get(app, "/api/senso/checks")
    if senso and senso.get("checks"):
        doc = senso.get("order_document") or {}
        n = len(senso["checks"])
        ok_n = sum(1 for c in senso["checks"] if str(c.get("label") or c.get("verdict") or "").lower() in ("verified", "supported", "ok", "match"))
        rows.append(_row("Senso", "Checks the sheet's sentences", n, "sentences checked",
                         "Against the order document%s%s; label: %s." % (" (version %s)" % doc.get("version_id") if doc.get("version_id") else "",
                                                                         " titled %r" % doc.get("title") if doc.get("title") else "", senso.get("label")),
                         "/api/senso/checks", not senso.get("error"), "run for this sheet's hash, ran %s" % senso.get("ran_at")))
    else:
        absent.append({"tool": "Senso", "why": "no check has run for the current sheet"})
    # Superlinked SIE
    readers = ((state.get("readers") or {}).get("readers")) or []
    tr = state.get("two_readers") or {}
    sie = next((r for r in readers if str(r.get("extractor", "")).startswith("sie:")), None)
    if sie:
        ref = next((r for r in readers if r is not sie), {}) or {}
        from signoff.obs.egress import rows as ledger_rows
        embeds = sum(1 for r in ledger_rows("all") if r.get("recipient", "").startswith("sie") and "embed" in (r.get("purpose") or "").lower())
        rows.append(_row("Superlinked SIE", "Second reader of pages", sie.get("pages_read"), "pages read",
                         "%s read %s pages (%s statements); %s read %s; the two read %s figures differently, %s only the reference found; %s embedding calls in the ledger."
                         % (sie["extractor"], sie.get("pages_read"), sie.get("statements"), ref.get("extractor"), ref.get("pages_read"),
                            (tr.get("strict_mode_measured") or {}).get("real_disagreements_caught"), (tr.get("strict_mode_measured") or {}).get("figures_blocked_that_only_the_reference_found"), embeds),
                         "/api/state (readers, two_readers)", False, "saved run (%s)" % (state.get("readers") or {}).get("made_at")))
    else:
        absent.append({"tool": "Superlinked SIE", "why": "no second reader's run for this sheet"})
    # Persona
    persona = await _get(app, "/api/issuer/persona/status")
    if persona and persona.get("inquiry_id"):
        rows.append(_row("Persona", "Verifies the signer", 1, "identity inquiry",
                         "Inquiry %s: %s (%s)." % (persona["inquiry_id"], persona.get("status"), "sandbox" if persona.get("sandbox") else "production"),
                         "/api/issuer/persona/status", bool(persona.get("verified")), "inquiry made in this run"))
    else:
        absent.append({"tool": "Persona", "why": "no identity inquiry started"})
    # Firedrill
    fd = await asyncio.to_thread(_firedrill)
    if fd:
        c = fd["campaigns"]
        last = c[-1]
        crit = {k: v for k, v in last["scores"].items()}
        names = {k: v["average"] for c_ in c for k, v in c_["scores"].items()}
        holds = last["scores"].get("Holds the sheet")
        rerun = len(c) > 1 and any(all(v["met"] for v in c_["scores"].values()) for c_ in c[1:])
        rows.append(_row("Firedrill", "Attacks written by others", len(c), "campaigns run",
                         "Campaigns %s. Scores of the latest: %s. Re-run after the fix with every criterion met: %s." % (
                             ", ".join(x["id"][:8] for x in c), "; ".join("%s %s (threshold %s)" % (k, v["average"], v["threshold"]) for k, v in crit.items()) or "none",
                             "yes" if rerun else "no"),
                         "evals/firedrill/*/report.txt", False, "saved runs (latest %s)" % last["saved"]))
    # Cognee
    cog = await _get(app, "/api/graph/cognee")
    if cog and cog.get("configured") and (cog.get("datasets") or cog.get("log")):
        rows.append(_row("Cognee", "Facts held by owner", len(cog.get("datasets") or {}), "datasets",
                         "Backend: %s; %d identities; %d writes refused of %d logged." % (cog.get("backend"), len(cog.get("identities") or {}),
                                                                                         len(cog.get("refused") or []), len(cog.get("log") or [])),
                         "/api/graph/cognee", True, "live read just now"))
    else:
        absent.append({"tool": "Cognee", "why": "no datasets or log entries held for this sheet"})
    return {"tools": rows, "absent": absent, "sheet": sheet_id, "line_id": line["line_id"], "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
