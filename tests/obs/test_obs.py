import time

from signoff import obs


def test_obs_never_raises_and_never_blocks(monkeypatch):
    monkeypatch.setattr(obs.config, "env", lambda name, default=None: None)  # no key: everything is a no-op
    t0 = time.time()
    sid = obs.session("sheet1", experiments=[{"key": "reader_model", "variant": "sonnet"}])
    for i in range(50):
        obs.tool_call("x", {"i": i}, object(), True, 1.0)
    obs.set_experiments(None)
    assert sid.startswith("sheet1-") and time.time() - t0 < 1.0
    obs.flush()  # drain while the key is still hidden, so no event is sent after the test


def test_timed_passes_result_and_exception_through():
    assert obs.timed("t", {}, lambda: 5) == 5
    try:
        obs.timed("t", {}, lambda: 1 / 0)
    except ZeroDivisionError:
        pass
    else:
        raise AssertionError


def test_events_are_kept_in_a_local_log_with_timings(monkeypatch, tmp_path):
    monkeypatch.setattr(obs, "LOG", tmp_path / "events.jsonl")
    obs.session("sheetX")
    obs.tool_call("store.search_catalog", {"q": "a"}, {"n": 1}, True, 120.0)
    obs.tool_call("check_run", {}, {}, False, 5.0, error="boom")
    rows = obs.recent(10, sheet_id="sheetX")
    assert [r["name"] for r in rows] == ["store.search_catalog", "check_run"]
    assert rows[0]["duration_ms"] == 120.0 and rows[0]["success"] is True and rows[1]["error"] == "boom"
    assert rows[0]["at"] < rows[0]["ended_at"] and rows[0]["session_id"].startswith("sheetX-")
    assert obs.recent(1)[0]["name"] == "check_run"
