"""The Statsig gate `sie_reader`: on = the engine's strict reading mode "both must agree" (a figure counts only when both readers,
Sonnet and the SIE model, report it), off = its default "disagreement blocks".

A background thread polls the gate every few seconds. On a change it switches the engine's reader, tags the Amplitude
session with the arm, and sends one `gate.changed` tool-call event carrying the outcome before and after. Never raises,
never blocks a request, does nothing once the sheet is signed.

A local override (POST /api/gate/override, Statsig's own `override_gate`) exists for a rehearsal without the console; the
status says `source: "local override"` while it is set.
"""
import datetime
import json
import logging
import pathlib
import threading
import time

from signoff import config, obs

log = logging.getLogger("signoff.gate")
ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
GATE = "sie_reader"
POLL_SECONDS = 3.0
_lock = threading.RLock()
_thread: threading.Thread | None = None
_sdk = None
_user = None
_override: bool | None = None
HISTORY = ROOT / "data" / "egress" / "gate_history.json"
_s = {"value": False, "arm": "disagreement-blocks", "changed_at": None, "polled_at": None, "source": "statsig", "error": None,
      "exists": None, "history": [], "refused": None}


def _save_history() -> None:
    try:
        HISTORY.parent.mkdir(parents=True, exist_ok=True)
        HISTORY.write_text(json.dumps(_s["history"]))
    except Exception:  # noqa: BLE001
        pass


try:
    _s["history"] = json.loads(HISTORY.read_text())[-20:] if HISTORY.exists() else []
except Exception:  # noqa: BLE001
    pass


def decision(evid: dict, value: bool) -> dict:
    """The screen's words, decided by code from the evidence (never by Amplitude, which only records the change)."""
    v = verdict_from(evid)
    ever_on = any(h["value"] for h in _s["history"])
    who = "code, from the engine's two-reader measurement"
    if v is None:
        return {"decision": None, "text": None, "decided_by": who}
    pick = ""
    if evid["picks_changed"]:
        c = evid["picks_changed"][0]
        pick = " and changed the %s pick (%s $%.2f to %s $%.2f, $%.2f more)" % (
            c["line_id"], c["one_reader"]["title"], c["one_reader"]["price_cents"] / 100,
            c["both_must_agree"]["title"], c["both_must_agree"]["price_cents"] / 100, evid["extra_cost_cents"] / 100)
    cost = "blocked %s right figures only the reference found, moved %s candidates to unclear%s" % (
        evid.get("figures_blocked_that_only_the_reference_found"), evid.get("moved_to_unclear"), pick)
    if v == "switch back":
        name = "switch back advised (the gate is on)" if value else ("switched back" if ever_on else "not adopted")
        return {"decision": name, "decided_by": who,
                "text": "%s: \"both must agree\" caught %s real disagreements but %s." % (name.capitalize(), evid.get("real_disagreements_caught"), cost)}
    return {"decision": "kept" if value else "not adopted", "decided_by": who,
            "text": "\"Both must agree\" caught %s real disagreements and changed no pick and no spend (it %s)." % (evid.get("real_disagreements_caught"), cost)}


MODES = {True: "both must agree", False: "disagreement blocks"}  # the engine's reading modes the gate switches between
ARM_NAMES = {True: "both-must-agree", False: "disagreement-blocks"}


def _arm(value: bool) -> str:
    return ARM_NAMES[bool(value)]


def _engine():
    from signoff.engine import state
    return state


def evidence() -> dict:
    """What the gate's strict mode ("both must agree") does against the default ("disagreement blocks"), measured by the engine
    in code on the sheet as on disk (`two_readers.strict_mode_measured`), plus each reader's cost and time per page."""
    try:
        st = _engine().get_state()
        tr = st.get("two_readers") or {}
        m = tr.get("strict_mode_measured") or {}
        if not m:
            return {"error": "the engine reports no two_readers measurement (no second reader's run for this sheet)"}
        rd = {r["extractor"]: r for r in ((st.get("readers") or {}).get("readers") or [])}
        per_page = {name: {"reader": rid, "pages": (rd.get(rid) or {}).get("pages_read"),
                           "seconds_median": (rd.get(rid) or {}).get("seconds_per_page_median"),
                           "cost": (rd.get(rid) or {}).get("cost")}
                    for name, rid in (("reference", tr.get("reference")), ("second", tr.get("second")))}
        return {"mode_now": tr.get("mode"), "reference": tr.get("reference"), "second": tr.get("second"),
                "figures_agreed": m.get("figures_agreed"), "real_disagreements_caught": m.get("real_disagreements_caught"),
                "figures_blocked_that_only_the_reference_found": m.get("figures_blocked_that_only_the_reference_found"),
                "figures_only_the_second_reader_found": m.get("figures_only_the_second_reader_found"),
                "candidates_changed": m.get("candidates_changed"), "moved_to_unclear": m.get("moved_to_unclear"),
                "picks_changed": m.get("picks_changed") or [],
                "total_cents": {"one_reader": m.get("total_cents_one_reader"), "both_must_agree": m.get("total_cents_both_must_agree")},
                "extra_cost_cents": (m.get("total_cents_both_must_agree") or 0) - (m.get("total_cents_one_reader") or 0),
                "live_tally": {k: tr.get(k) for k in ("figures_agreed", "figures_disagreed", "only_reference_found", "only_second_found")},
                "per_page": per_page, "measured_on": m.get("measured_on")}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__ + ": " + str(e)[:140]}


def verdict_from(evid: dict) -> str | None:
    """Code decides, from the engine's measurement. The strict mode is kept only if it costs nothing in what is bought: no pick
    changes and no extra spend. Catching real disagreements is its benefit and is shown beside the cost, but it does not buy a
    dearer or different pick on its own."""
    if not evid or evid.get("error") or evid.get("picks_changed") is None:
        return None
    return "switch back" if (evid["picks_changed"] or (evid.get("extra_cost_cents") or 0) > 0) else "kept"


def outcome() -> dict:
    """Each reader's own numbers from the engine's `readers` block (pages, statements, agreement of outcomes, cost and time per
    page); `deciding` is the reading mode the engine uses now."""
    out = {"deciding": None, "arms": {}}
    try:
        st = _engine().get_state()
        rd = st.get("readers") or {}
        tr = st.get("two_readers") or {}
        out["deciding"] = tr.get("mode")
        out["signed"] = bool((st.get("seal") or {}).get("signed"))
        out["live_counts"] = st.get("counts")
        by = {r["extractor"]: r for r in rd.get("readers", [])}
        for arm, rid in (("sonnet", tr.get("reference")), ("sie-qwen", tr.get("second"))):
            r = by.get(rid) or {}
            out["arms"][arm] = {"reader": rid, "pages_read": r.get("pages_read"), "statements": r.get("statements"),
                                "candidates": r.get("candidates"), "statement": r.get("statement"),
                                "cost": r.get("cost"), "seconds_per_page_median": r.get("seconds_per_page_median")}
        out["note"] = rd.get("note")
    except Exception as e:  # noqa: BLE001
        out["error"] = type(e).__name__ + ": " + str(e)[:120]
    return out


def _read_gate() -> bool:
    global _sdk, _user
    if _override is not None:
        return _override
    if _sdk is None:
        from statsig_python_core import Statsig, StatsigOptions, StatsigUser
        o = StatsigOptions()
        o.environment = "development"
        _sdk = Statsig(config.env("STATSIG_SERVER_SECRET"), o)
        obs.egress("statsig", "gate reader: sync of gate rules, then one check of sie_reader per poll (this row once)",
                   {"gate": GATE, "user_id": "signoff-demo"}, ["none"])
        _sdk.initialize().wait()
        _user = StatsigUser("signoff-demo")
    g = _sdk.get_feature_gate(_user, GATE)
    _s["exists"] = bool(getattr(g, "rule_id", "")) or bool(g.value)
    return bool(_sdk.check_gate(_user, GATE))


def _apply(value: bool) -> None:
    """Switch the engine's reader to the arm and record before and after. Called only when the value changed."""
    arm = _arm(value)
    obs.egress("statsig", "gate value changed: exposure event", {"gate": GATE, "value": value, "user_id": "signoff-demo"}, ["none"])
    before = outcome()
    try:
        _engine().set_reading_mode(MODES[bool(value)])
    except Exception as e:  # noqa: BLE001  (the engine refuses after signing, or the run is missing)
        _s["refused"] = type(e).__name__ + ": " + str(e)[:120]
        obs.tool_call("gate.changed", {"gate": GATE, "value": value, "arm": arm}, {"refused": _s["refused"]}, False, 0.0,
                      _s["refused"])
        return
    _s["refused"] = None
    after = outcome()
    now = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    _s.update(value=value, arm=arm, changed_at=now)
    _s["history"] = (_s["history"] + [{"at": now, "value": value, "arm": arm}])[-20:]
    _save_history()
    obs.set_experiments([{"key": GATE, "variant": arm}])
    obs.tool_call("gate.changed", {"gate": GATE, "value": value, "arm": arm, "source": _s["source"]},
                  {"before": before, "after": after, "decision": decision(evidence(), value)["decision"]}, True, 0.0)


def poll_once() -> None:
    try:
        st = _engine().get_state()
        if (st.get("seal") or {}).get("signed"):
            _s["polled_at"] = time.time()
            return  # the sheet is signed: no switching any more
        _s["source"] = "local override" if _override is not None else "statsig"
        value = _read_gate()
        _s["polled_at"] = time.time()
        _s["error"] = None
        if value != _s["value"]:
            _apply(value)
    except Exception as e:  # noqa: BLE001
        _s["error"] = type(e).__name__ + ": " + str(e)[:140]


def _loop() -> None:
    while True:
        poll_once()
        time.sleep(POLL_SECONDS)


def start() -> None:
    """Start the poller once (no-op without a Statsig key, or with SIGNOFF_GATE=off)."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return
        if config.env("SIGNOFF_GATE") == "off" or not config.env("STATSIG_SERVER_SECRET"):
            return
        _thread = threading.Thread(target=_loop, name="statsig-gate", daemon=True)
        _thread.start()


def set_override(value: bool | None) -> None:
    global _override
    _override = value
    poll_once()


def status() -> dict:
    out = outcome()
    evid = evidence()
    dec = decision(evid, _s["value"])
    return {"gate": GATE, "value": _s["value"], "arm": _s["arm"], "deciding_reader": out.get("deciding"),
            "decision": dec["decision"], "decision_text": dec["text"], "decided_by": dec["decided_by"],
            "recorded_in": "Amplitude (event gate.changed, session experiment sie_reader)", "evidence": evid,
            "source": "local override" if _override is not None else "statsig",
            "gate_exists_in_statsig": _s["exists"], "changed_at": _s["changed_at"], "history": _s["history"],
            "polling": bool(_thread and _thread.is_alive()), "poll_seconds": POLL_SECONDS,
            "last_polled_ago_s": round(time.time() - _s["polled_at"], 1) if _s["polled_at"] else None,
            "verdict": verdict_from(evid), "refused": _s["refused"], "error": _s["error"],
            "outcome": {"arms": out.get("arms"), "note": out.get("note"), "signed": out.get("signed")}}
