"""Amplitude Agent Analytics events: one session per sheet run, one tool-call event per tool use.

`session(sheet_id)` and `tool_call(name, input, output, success, latency_ms)` never raise and never wait: events go on
a queue and one background thread talks to Amplitude. `flush()` waits (bounded); it also runs at interpreter exit.
Without AMPLITUDE_AI_API_KEY every call is a no-op that only counts.
"""
import atexit
import json
import datetime
import logging
import pathlib
import queue
import sys
import threading
import time
import uuid

from signoff import config
from signoff.obs import egress as _egress_module  # noqa: E402  (the ledger; `egress` below is its entry point)

log = logging.getLogger("signoff.obs")
AGENT_ID = "signoff-shopper"
_q: "queue.Queue" = queue.Queue(maxsize=5000)
_lock = threading.Lock()
_worker: threading.Thread | None = None
_state = {"session_id": None, "sheet_id": None, "experiments": None}
stats = {"queued": 0, "sent": 0, "delivered": 0, "dropped": 0, "last_error": None, "last_status": None}
_ai = None  # AmplitudeAI, created by the worker
_agent = None
_sess = None  # amplitude Session object of the current run
_closing = False


def _clip(v, n=1500):
    """Small JSON-able copy of an input or output: long strings are cut, nothing else is touched."""
    try:
        if isinstance(v, str):
            return v if len(v) <= n else v[:n] + "…"
        if isinstance(v, dict):
            return {str(k): _clip(x, n) for k, x in list(v.items())[:30]}
        if isinstance(v, (list, tuple)):
            return [_clip(x, n) for x in list(v)[:30]]
        if isinstance(v, (int, float, bool)) or v is None:
            return v
        return _clip(str(v), n)
    except Exception:  # noqa: BLE001
        return None


def _put(item: tuple) -> None:
    global _worker
    try:
        if _closing or config.env("SIGNOFF_OBS") == "off":  # off: tests and dry runs send nothing
            if item[0] == "signal":
                item[1].set()
            stats["dropped"] += 1
            return
        with _lock:
            if _worker is None or not _worker.is_alive():
                _worker = threading.Thread(target=_run, name="obs-worker", daemon=True)
                _worker.start()
        _q.put_nowait(item)
        stats["queued"] += 1
    except Exception:  # noqa: BLE001
        stats["dropped"] += 1


def session(sheet_id: str, experiments: list[dict] | None = None) -> str:
    """Start a new session for this sheet run (ends the previous one). Returns its id. `experiments` is the Statsig
    variant list, e.g. [{"key": "reader_model", "variant": "arcee"}]; it is carried by every event of the session."""
    sid = f"{sheet_id}-{datetime.datetime.now().strftime('%H%M%S')}-{uuid.uuid4().hex[:4]}"
    try:
        _state.update(session_id=sid, sheet_id=sheet_id, experiments=experiments)
        _put(("session", sid, sheet_id, experiments))
    except Exception:  # noqa: BLE001
        pass
    return sid


def set_experiments(experiments: list[dict] | None) -> None:
    """Attach (or change) experiment variants on the running session and the events after this call."""
    try:
        _state["experiments"] = experiments
        _put(("experiments", experiments))
    except Exception:  # noqa: BLE001
        pass


_DEFAULT_LOG = pathlib.Path(__file__).resolve().parent.parent.parent / "data" / "obs" / "events.jsonl"
LOG = _DEFAULT_LOG
_log_lock = threading.Lock()


def _log_local(name: str, ms: float, ok: bool, error: str | None) -> None:
    """Every tool-call event also goes to a local JSON-lines log (name, at, duration_ms, success), whatever Amplitude does."""
    try:
        if LOG == _DEFAULT_LOG and "pytest" in sys.modules:  # unit tests of other streams must not write the real log
            return
        end = datetime.datetime.now().astimezone()
        row = {"name": name, "at": (end - datetime.timedelta(milliseconds=ms or 0)).isoformat(timespec="milliseconds"),
               "ended_at": end.isoformat(timespec="milliseconds"), "duration_ms": round(float(ms or 0), 1), "success": bool(ok),
               "session_id": _state.get("session_id"), "sheet_id": _state.get("sheet_id")}
        if error:
            row["error"] = str(error)[:200]
        with _log_lock:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a") as f:
                f.write(json.dumps(row) + "\n")
    except Exception:  # noqa: BLE001
        pass


def recent(n: int = 200, session_id: str | None = None, sheet_id: str | None = None) -> list[dict]:
    """The last n tool-call events from the local log, oldest first: {name, at, ended_at, duration_ms, success, session_id,
    sheet_id[, error]}. `session_id` or `sheet_id` narrow it. Never raises."""
    try:
        with _log_lock:
            lines = LOG.read_text().splitlines() if LOG.exists() else []
        rows = [json.loads(l) for l in lines[-20000:] if l.strip()]
        if session_id:
            rows = [r for r in rows if r.get("session_id") == session_id]
        if sheet_id:
            rows = [r for r in rows if r.get("sheet_id") == sheet_id]
        return rows[-n:]
    except Exception:  # noqa: BLE001
        return []


def tool_call(name: str, input: dict | None = None, output=None, success: bool = True, latency_ms: float = 0.0,
              error: str | None = None) -> None:
    try:
        if _state["session_id"] is None:
            session("sheet1")
        _log_local(name, latency_ms, success, error)
        _put(("tool", name, _clip(input), _clip(output), bool(success), float(latency_ms or 0.0), error))
    except Exception:  # noqa: BLE001
        pass


def timed(name: str, input: dict | None, fn, summarise=lambda r: r):
    """Run fn(), emit one tool_call with its latency and outcome, return fn's result (exceptions pass through)."""
    t0 = time.perf_counter()
    try:
        r = fn()
    except Exception as e:  # noqa: BLE001
        tool_call(name, input, None, False, (time.perf_counter() - t0) * 1000, type(e).__name__ + ": " + str(e)[:200])
        raise
    try:
        out = summarise(r)
    except Exception:  # noqa: BLE001
        out = None
    tool_call(name, input, out, True, (time.perf_counter() - t0) * 1000)
    return r


def flush(timeout: float = 8.0) -> None:
    """Wait (bounded) until queued events have been handed to Amplitude and its buffer is sent."""
    try:
        _put(("flush",))
        deadline = time.time() + timeout
        while time.time() < deadline and not _q.empty():
            time.sleep(0.05)
        done = threading.Event()
        _put(("signal", done))
        done.wait(max(0.0, deadline - time.time()))
    except Exception:  # noqa: BLE001
        pass


def _init():
    global _ai, _agent
    key = config.env("AMPLITUDE_AI_API_KEY")
    if not key:
        raise RuntimeError("AMPLITUDE_AI_API_KEY missing")
    from amplitude_ai import AIConfig, AmplitudeAI, ContentMode
    mode = "full" if _content_full() else "metadata_only"
    def delivered(event, code, message=None):
        stats["last_status"] = code
        if code == 200:
            stats["delivered"] += 1
        else:
            stats["last_error"] = f"amplitude status {code}: {str(message)[:120]}"

    cfg = AIConfig(content_mode=ContentMode(mode), on_event_callback=delivered)
    _ai = AmplitudeAI(api_key=key, config=cfg)
    _agent = _ai.agent(AGENT_ID, user_id="signoff-demo", description="Shopping agent that buys under someone else's limits",
                       env=config.env("SIGNOFF_ENV", "hackathon"))


def _content_full() -> bool:
    return (config.env("SIGNOFF_AMPLITUDE_CONTENT", "metadata_only") or "metadata_only").lower() == "full"


def _end_session():
    global _sess
    if _sess is not None:
        try:
            # Session.track_session_end is shadowed by its constructor flag; entering and leaving the context emits the end
            _sess.__enter__()
            _sess.__exit__(None, None, None)
        except Exception as e:  # noqa: BLE001
            stats["last_error"] = type(e).__name__ + ": " + str(e)[:160]
        _sess = None


def _handle(item: tuple) -> None:
    global _sess
    kind = item[0]
    if kind == "signal":
        item[1].set()
        return
    if config.env("AMPLITUDE_AI_API_KEY") is None:
        stats["dropped"] += 1
        return
    if _ai is None:
        if kind == "flush":
            return
        _init()
    if kind == "session":
        egress("amplitude", "session start", {"session_id": item[1], "sheet_id": item[2], "experiments": item[3]}, ["none"])
        _end_session()
        _sess = _agent.session(session_id=item[1], user_id="signoff-demo", experiments=item[3],
                               context={"sheet_id": item[2]}, auto_flush=False)
    elif kind == "experiments":
        if _sess is not None:
            _sess.add_experiments(item[1])
    elif kind == "tool":
        if _sess is None:
            _sess = _agent.session(session_id=_state["session_id"] or "sheet1", user_id="signoff-demo",
                                   experiments=_state["experiments"], auto_flush=False)
        _, name, inp, out, ok, ms, err = item
        meta = {"tool": name, "success": ok, "latency_ms": ms, "error": err}
        if _content_full():  # content mode "full": inputs and outputs travel, unless code finds a sealed value in them
            found = _egress_module.detect(json.dumps({"input": inp, "output": out}, default=str))
            if found:
                inp, out = {"redacted_by_code": sorted({h["class"] for h in found})}, None
            egress("amplitude", "agent tool-call event: " + name, {**meta, "input": inp, "output": out}, None)
        else:  # metadata_only (the default): the SDK drops input and output, so only the metadata is sent and recorded
            inp = out = None
            egress("amplitude", "agent tool-call event (metadata only): " + name, meta, ["none"])
        kw = {"input": inp, "output": out}
        if err:
            kw["error_message"] = err
        _sess.track_tool_call(name, ms, ok, **kw)
        stats["sent"] += 1
    elif kind == "flush":
        for fut in _ai.flush() or []:
            if fut is not None:
                try:
                    fut.result(timeout=6)
                except Exception as e:  # noqa: BLE001
                    stats["last_error"] = type(e).__name__ + ": " + str(e)[:160]


def _run() -> None:
    flushed = 0
    while not _closing:
        try:
            item = _q.get(timeout=3)
        except queue.Empty:  # idle: hand what Amplitude's buffer holds to the network, without waiting for it
            if _ai is not None and stats["sent"] != flushed:
                flushed = stats["sent"]
                try:
                    _ai.flush()
                except Exception as e:  # noqa: BLE001
                    stats["last_error"] = type(e).__name__ + ": " + str(e)[:160]
            continue
        try:
            _handle(item)
        except Exception as e:  # noqa: BLE001
            stats["last_error"] = type(e).__name__ + ": " + str(e)[:160]
            stats["dropped"] += 1
            log.warning("obs: %s", stats["last_error"])
            if item[0] == "signal":
                item[1].set()


def shutdown() -> None:
    """Flush, end the session, close the SDK. Safe to call twice; runs at interpreter exit."""
    global _closing
    try:
        if _ai is None and _q.empty():  # nothing was ever sent: do not start the SDK just to close it
            _closing = True
            return
        flush(5.0)
        _closing = True
        if _ai is not None:
            _end_session()
            _ai.shutdown()
    except Exception:  # noqa: BLE001
        pass


atexit.register(shutdown)


def egress(recipient: str, purpose: str, payload=None, fact_classes=None, kind: str | None = None,
           block_on_hit: bool = False, mask: list | None = None) -> dict:
    """Record one outbound message in the ledger (signoff/obs/egress.py). Never raises, never blocks; returns the row,
    whose `sealed_hits` lists any sealed value found in a payload to a store."""
    return _egress_module.record(recipient, purpose, payload, fact_classes, kind, block_on_hit, mask)
