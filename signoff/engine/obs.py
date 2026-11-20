"""Events for `signoff.obs` (the STORE stream's Amplitude sender). Never raises, never waits; a no-op
until that module is merged or when it has no key."""
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


def ms_since(started):
    return int((time.perf_counter() - started) * 1000)
