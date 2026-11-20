"""Events for `signoff.obs` (the STORE stream's Amplitude sender). Never raises, never waits; a no-op
until that module is merged or when it has no key."""
import os
import time


def tool_call(name, input=None, output=None, success=True, latency_ms=0):
    try:
        from signoff import obs
        send = getattr(obs, "tool_call", None)
        if send:
            send(name, input or {}, output or {}, success, latency_ms)
    except Exception:  # noqa: BLE001
        pass


def session(sheet_id):
    try:
        from signoff import obs
        start = getattr(obs, "session", None)
        if start:
            start(sheet_id)
    except Exception:  # noqa: BLE001
        pass


def egress(recipient, purpose, payload, fact_classes):
    """The outbound ledger (`signoff.obs.egress`, the STORE stream's): what was sent to whom, and which kinds
    of fact it held. Called at every place ENGINE code sends anything out. A no-op until that function exists."""
    if os.environ.get("SIGNOFF_EGRESS") == "off":  # tests: a faked call must not leave a row in the real ledger
        return
    try:
        from signoff import obs
        record = getattr(obs, "egress", None)
        if record:
            record(recipient, purpose, payload, list(fact_classes))
    except Exception:  # noqa: BLE001
        pass


def ms_since(started):
    return int((time.perf_counter() - started) * 1000)
