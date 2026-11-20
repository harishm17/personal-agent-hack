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
_s = {"value": False, "arm": "sonnet", "changed_at": None, "polled_at": None, "source": "statsig", "error": None,
      "exists": None, "history": [], "refused": None}


def _arm(value: bool) -> str:
    return "sie-qwen" if value else "sonnet"


def _engine():
    from signoff.engine import state
    return state


def _stating_every_figure(arm: str) -> dict:
    """Pool products (product and line pairs, as the engine counts) whose deciding figures the arm's own run states
    with the quote found in the text and not marked unsure."""
    try:
        sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
        need = {l["id"]: {t["figure"] for lim in l["limits"] for t in lim["terms"] if t["source"] == "store"}
                for l in sheet["lines"]}
        run = ROOT / "data" / "figures" / "_runs" / ARMS[arm][1]
        have: dict = {}
        for f in run.glob("*.json"):
            for r in json.loads(f.read_text()):
                if r.get("span_found_in_text") and not r.get("unsure"):
                    have.setdefault((r["store"], r["product_id"]), set()).add(r["figure"])
        total = ok = 0
        for f in (ROOT / "data" / "pool").glob("*.json"):
            for p in json.loads(f.read_text()):
                for lid in p["line_ids"]:
                    total += 1
                    ok += need[lid] <= have.get((p["store"], p["product_id"]), set())
        return {"pairs": total, "state_every_figure": ok}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


def outcome() -> dict:
    """Both arms side by side from the engine's `readers` block (agreement, cost, seconds) plus each arm's own count of
    products stating every figure; `deciding` is the reader the engine uses now."""
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
            out["arms"][arm] = {"reader": rid, "agreement": r.get("agreement"), "figures_counted": r.get("figures_counted"),
                                "same_as_reference": r.get("same_as_reference"), "cost": r.get("cost"),
                                "seconds_per_product_median": r.get("seconds_per_product_median"),
                                "products_read": r.get("products_read"), **_stating_every_figure(arm)}
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
        _sdk.initialize().wait()
        _user = StatsigUser("signoff-demo")
    g = _sdk.get_feature_gate(_user, GATE)
    _s["exists"] = bool(getattr(g, "rule_id", "")) or bool(g.value)
    return bool(_sdk.check_gate(_user, GATE))


def _apply(value: bool) -> None:
    """Switch the engine's reader to the arm and record before and after. Called only when the value changed."""
    arm = _arm(value)
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
    obs.set_experiments([{"key": GATE, "variant": arm}])
    obs.tool_call("gate.changed", {"gate": GATE, "value": value, "arm": arm, "source": _s["source"]},
                  {"before": before, "after": after, "kept": _verdict(before, after)}, True, 0.0)


def _verdict(before: dict, after: dict) -> str | None:
    """'kept' when the new reader agrees with the reference on at least 95% of figures and states every figure on at
    least as many products; otherwise 'switch back'. Code decides, from the numbers above."""
    try:
        a = after["arms"][_s["arm"]]
        base = after["arms"]["sonnet"]
        if _s["arm"] == "sonnet":
            return None
        ok = (a["agreement"] or 0) >= 0.95 and (a["state_every_figure"] or 0) >= (base["state_every_figure"] or 0)
        return "kept" if ok else "switch back"
    except Exception:  # noqa: BLE001
        return None


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
    return {"gate": GATE, "value": _s["value"], "arm": _s["arm"], "deciding_reader": out.get("deciding"),
            "source": "local override" if _override is not None else "statsig",
            "gate_exists_in_statsig": _s["exists"], "changed_at": _s["changed_at"], "history": _s["history"],
            "polling": bool(_thread and _thread.is_alive()), "poll_seconds": POLL_SECONDS,
            "last_polled_ago_s": round(time.time() - _s["polled_at"], 1) if _s["polled_at"] else None,
            "verdict": _verdict(out, out), "refused": _s["refused"], "error": _s["error"],
            "outcome": {"arms": out.get("arms"), "note": out.get("note"), "signed": out.get("signed")}}
