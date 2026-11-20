"""The Statsig gate `sie_reader`: on = the SIE reader decides the figures, off = the Sonnet reference.

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
ARMS = {  # arm name -> (engine reader name, folder of that reader's own run, reader id in /api/state `readers`)
    "sonnet": (None, "claude-sonnet-5-5", "anthropic:claude-sonnet-5-5"),
    "sie-qwen": ("sie:Qwen/Qwen3.8-27B-FP8", "sie-Qwen-Qwen3.8-27B-FP8", "sie:Qwen/Qwen3.8-27B-FP8"),
}
_lock = threading.RLock()
_thread: threading.Thread | None = None
_sdk = None
_user = None
_override: bool | None = None
HISTORY = ROOT / "data" / "egress" / "gate_history.json"
_s = {"value": False, "arm": "sonnet", "changed_at": None, "polled_at": None, "source": "statsig", "error": None,
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
    d = (evid or {}).get("disagreements") or {}
    if v is None:
        return {"decision": None, "text": None, "decided_by": "code, from the run files"}
    acc = evid["products_accepted"]
    extra = "It also read %d figure(s) the reference did not count; they move %d candidate(s) inside the limits and are listed for a check." % (
        d.get("small_only", 0), len(evid.get("inside_only_small_reader") or []))
    if v == "switch back":
        name = "switch back advised (the gate is on)" if value else ("switched back" if ever_on else "not adopted")
        text = "%s: on %d quote(s) the small reader read a different number from the reference. %s It accepted %d more products (%d against %d)." % (
            name.capitalize(), d.get("different_value", 0), extra, evid["small_accepts_more"], acc["sie-qwen"], acc["sonnet"])
        return {"decision": name, "text": text, "decided_by": "code, from the two readers' run files"}
    return {"decision": "kept" if value else "not adopted",
            "text": "The small reader never read a quote to a different number than the reference. " + extra,
            "decided_by": "code, from the two readers' run files"}


def _arm(value: bool) -> str:
    return "sie-qwen" if value else "sonnet"


def _engine():
    from signoff.engine import state
    return state


def _arm_figures(arm: str) -> list[dict]:
    """The arm's own figures, spans re-checked against the pool text exactly as the engine does."""
    from signoff.engine import rules
    eng = _engine()
    folder = ROOT / "data" / "figures" / ("_runs/" + ARMS[arm][1] if arm != "sonnet" else "")
    figs = eng._read_dir(folder) if arm != "sonnet" else eng._read_dir(ROOT / "data" / "figures")
    text = {(p["store"], p["product_id"]): p.get("text") for p in eng._s["pool"]}
    for f in figs:
        f["span_found_in_text"] = rules.span_found(f, text.get((f["store"], f["product_id"])))
    return figs


_arm_cache: dict = {}


def _arm_state(arm: str) -> dict:
    """What the engine's own rules (rules.build_state) give with this arm's figures on the current limits."""
    import copy
    from signoff.engine import rules
    eng = _engine()
    key = (arm, eng._s.get("version"))
    if key not in _arm_cache:
        with eng._lock:
            sheet, pool, answers, strikes, mode = (copy.deepcopy(eng._s["sheet"]), eng._s["pool"], eng._s["answers"],
                                                   copy.deepcopy(eng._s["strikes"]), eng._s["mode"])
        st = rules.build_state(sheet, pool, _arm_figures(arm), answers, strikes, mode)
        picks = {l["line_id"]: next((c for c in l["candidates"] if c["picked"]), None) for l in st["lines"]}
        inside = {c["id"]: {"line": l["line_id"], "title": c["product"]["title"], "store": c["product"]["store"]}
                  for l in st["lines"] for c in l["candidates"] if c["status"] == "inside"}
        _arm_cache.clear()
        _arm_cache[key] = {"counts": st["counts"], "inside": inside,
                           "picks": {k: (v and {"title": v["product"]["title"], "store": v["product"]["store"],
                                                "price_cents": v["product"]["price_cents"]}) for k, v in picks.items()}}
    return _arm_cache[key]


def _title(store: str, product_id: str) -> str:
    try:
        return next(p["title"] for p in _engine()._s["pool"] if p["store"] == store and p["product_id"] == product_id)
    except Exception:  # noqa: BLE001
        return product_id


def _same(a: dict, b: dict) -> bool:
    return (a.get("low"), a.get("high")) == (b.get("low"), b.get("high"))


def _shown(f: dict) -> str:
    lo, hi, u = f.get("low"), f.get("high"), f.get("unit") or ""
    return ("%g %s" % (lo, u)) if lo == hi else ("%g to %g %s" % (lo, hi, u))


def disagreements() -> dict:
    """Where the small reader and the reference reader differ, by code, on the same product and figure."""
    ref, small = _arm_figures("sonnet"), _arm_figures("sie-qwen")

    def idx(rows):
        return {(r["store"], r["product_id"], r["figure"]): r for r in rows}

    def counts(r):
        return bool(r and r.get("span_found_in_text") and not r.get("unsure"))

    a, b = idx(ref), idx(small)
    different, small_only, ref_only = [], [], []
    for k in sorted(set(a) | set(b)):
        ra, rb = a.get(k), b.get(k)
        row = {"store": k[0], "product_id": k[1], "product": _title(k[0], k[1]), "figure": k[2]}
        if counts(ra) and counts(rb) and not _same(ra, rb):
            different.append({**row, "quote": rb["quote"], "reference_read": _shown(ra), "small_read": _shown(rb),
                              "same_quote": ra["quote"] == rb["quote"]})
        elif counts(rb) and not counts(ra):
            small_only.append({**row, "quote": rb["quote"], "small_read": _shown(rb),
                               "reference": ("did not count it: " + (ra.get("unsure_reason") or "marked unsure")) if ra else "did not report it"})
        elif counts(ra) and not counts(rb):
            ref_only.append({**row, "quote": ra["quote"], "reference_read": _shown(ra)})
    return {"different_value": different, "small_only": small_only, "reference_only": ref_only}


def evidence() -> dict:
    """The numbers that decide keep or switch back: products accepted by each arm (the engine's own rules), how many
    more the small reader accepted, and every figure where the two disagree."""
    out = {}
    try:
        ref, small = _arm_state("sonnet"), _arm_state("sie-qwen")
        d = disagreements()
        n_ref, n_small = ref["counts"]["state_every_figure"], small["counts"]["state_every_figure"]
        only_small = [{"candidate": k, **v} for k, v in small["inside"].items() if k not in ref["inside"]]
        only_ref = [{"candidate": k, **v} for k, v in ref["inside"].items() if k not in small["inside"]]
        rd = {r["extractor"]: r for r in ((_engine().get_state().get("readers") or {}).get("readers") or [])}
        per_page = {arm: {"seconds_median": (rd.get(rid) or {}).get("seconds_per_product_median"),
                          "cost": (rd.get(rid) or {}).get("cost"), "pages": (rd.get(rid) or {}).get("products_read")}
                    for arm, (_, _, rid) in ARMS.items()}
        ex = next((x for x in d["different_value"] if x["figure"] == "overall_width"), (d["different_value"] or [None])[0])
        out = {"products_accepted": {"sonnet": n_ref, "sie-qwen": n_small, "of": ref["counts"]["products_found"]},
               "small_accepts_more": n_small - n_ref,
               "inside_limits": {"sonnet": ref["counts"]["inside_limits"], "sie-qwen": small["counts"]["inside_limits"]},
               "inside_only_small_reader": only_small, "inside_only_reference": only_ref, "per_page": per_page,
               "picks_differ_on": [l for l in ref["picks"] if (ref["picks"][l] or {}).get("title") != (small["picks"][l] or {}).get("title")],
               "disagreements": {k: len(v) for k, v in d.items()}, "figures_in_disagreement": d,
               "example": ex and {**ex, "sentence": "On %s the quote %r was read as %s by the reference and %s by the small reader." % (
                   ex["product"], ex["quote"], ex["reference_read"], ex["small_read"])}}
    except Exception as e:  # noqa: BLE001
        out = {"error": type(e).__name__ + ": " + str(e)[:140]}
    return out


def verdict_from(evid: dict) -> str | None:
    """Code decides, from the two readers' run files. The small reader is kept unless it ever reads the same quote to a
    different number than the reference (then which of them is right cannot be settled by code, and the reference stays the
    default). Extra figures it reads are not held against it (they may be right): they are counted and listed, with the
    candidates they move inside the limits, for a person to check. Stating more products is not by itself a reason to keep it."""
    dis = (evid or {}).get("disagreements")
    if dis is None:
        return None
    return "switch back" if dis["different_value"] else "kept"


def outcome() -> dict:
    """Both arms side by side from the engine's `readers` block (agreement, cost, seconds) plus each arm's products accepted
    under the engine's rules; `deciding` is the reader the engine uses now."""
    out = {"deciding": None, "arms": {}}
    try:
        st = _engine().get_state()
        rd = st.get("readers") or {}
        out["deciding"] = rd.get("deciding")
        out["signed"] = bool((st.get("seal") or {}).get("signed"))
        out["live_counts"] = st.get("counts")
        by = {r["extractor"]: r for r in rd.get("readers", [])}
        for arm, (_, _, rid) in ARMS.items():
            r = by.get(rid) or {}
            c = _arm_state(arm)["counts"]
            out["arms"][arm] = {"reader": rid, "agreement": r.get("agreement"), "figures_counted": r.get("figures_counted"),
                                "same_as_reference": r.get("same_as_reference"), "cost": r.get("cost"),
                                "seconds_per_product_median": r.get("seconds_per_product_median"),
                                "products_read": r.get("products_read"), "pairs": c["products_found"],
                                "state_every_figure": c["state_every_figure"]}
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
        _engine().set_reader(ARMS[arm][0])
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
