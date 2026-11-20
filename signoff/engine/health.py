"""Degraded paths, said out loud. Anything that falls back to something lesser notes it here, and the state
carries the list as `degraded` (empty when all is well). Nothing falls back silently."""
import threading

_lock = threading.Lock()
_notes = {}


def note(key: str, message: str) -> None:
    with _lock:
        _notes[key] = message


def clear(key: str) -> None:
    with _lock:
        _notes.pop(key, None)


def all() -> list:
    with _lock:
        return [{"what": k, "note": v} for k, v in sorted(_notes.items())]
