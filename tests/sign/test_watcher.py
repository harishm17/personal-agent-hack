"""Senso's background check runs for the active sheet at start and after a switch, with no phone open (G21)."""
from signoff.sign import api, senso

from .sheet4_state import build as build4
from .standin import FakeEngine


def setup(monkeypatch, engine):
    ran, loaded = [], []
    monkeypatch.setattr(senso, "configured", lambda: True)
    monkeypatch.setattr(api, "get_engine", lambda: engine)
    monkeypatch.setattr(senso, "run_checks", lambda state, h: (ran.append(h), senso.set_checks([{"verdict": "verified", "blocks": True}], h)))
    monkeypatch.setattr(senso, "load_documents", lambda sheet=None: loaded.append((sheet or {}).get("id")))
    monkeypatch.setattr(senso, "wait_processed", lambda timeout=0: {})
    senso.reset()
    senso._kick.clear()
    return ran, loaded


def test_the_first_look_loads_the_sheets_order_and_runs_the_check(monkeypatch):
    engine = FakeEngine(build4)
    ran, loaded = setup(monkeypatch, engine)
    mem = {}
    assert api._watch_tick(mem, now=100.0) == "ran"                  # at start: no phone, no request
    assert loaded == ["sheet4"] and ran == [engine.sheet_hash()]
    assert senso.checks()["for_hash"] == engine.sheet_hash()
    assert api._watch_tick(mem, now=101.0) == "current"              # nothing to do until something changes


def test_a_switched_sheet_is_checked_at_once(monkeypatch):
    engine = FakeEngine(build4)
    ran, loaded = setup(monkeypatch, engine)
    mem = {}
    api._watch_tick(mem, now=100.0)
    from .sheet3_state import build as build3
    engine.state = build3()                                          # the laptop switched to another sheet
    assert api._watch_tick(mem, now=100.1) == "ran"
    assert loaded == ["sheet4", "sheet3"] and len(ran) == 2 and ran[0] != ran[1]


def test_a_limit_change_waits_for_the_debounce_then_runs(monkeypatch):
    engine = FakeEngine(build4)
    ran, loaded = setup(monkeypatch, engine)
    mem = {}
    api._watch_tick(mem, now=100.0)
    engine.state["total_cents"] += 5                                 # the hash moves
    assert api._watch_tick(mem, now=200.0) == "waiting"
    assert api._watch_tick(mem, now=200.0 + api.DEBOUNCE_S + 0.1) == "ran" and len(ran) == 2


def test_nothing_runs_without_a_key_or_after_the_signature(monkeypatch):
    engine = FakeEngine(build4)
    ran, loaded = setup(monkeypatch, engine)
    monkeypatch.setattr(senso, "configured", lambda: False)
    assert api._watch_tick({}, now=1.0) == "not configured" and ran == []
    monkeypatch.setattr(senso, "configured", lambda: True)
    engine.state["seal"] = {"signed": True}
    assert api._watch_tick({}, now=1.0) == "signed" and ran == []


def test_the_app_starts_the_watcher_at_startup(monkeypatch):
    started = []
    monkeypatch.setattr(api, "ensure_watcher", lambda: started.append(1))
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    app = FastAPI()
    app.include_router(api.router)
    with TestClient(app):
        pass
    assert started and set(started) == {1}      # idempotent: a second call starts nothing
