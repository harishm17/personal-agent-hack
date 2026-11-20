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
