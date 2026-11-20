"""The sign tap never hangs: a slow Senso and a slow store cannot hold the request past about 8 seconds."""
import threading
import time

from signoff.sign import api, senso

from .standin import FakeCart

RELEASE = threading.Event()


class SlowCart(FakeCart):
    """Answers only after RELEASE is set (or 25 s), like a store that has stopped replying."""

    def create_carts(self, picks):
        self.calls.append(picks)
        RELEASE.wait(25)
        return super().create_carts(picks) if not self.fail else (_ for _ in ()).throw(RuntimeError("late"))


def sign_request(env):
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    started = time.time()
    r = env.client.post("/api/issuer/request", json=body)
    return r, time.time() - started


def test_slow_senso_and_slow_store_still_answer_within_ten_seconds(env, monkeypatch):
    RELEASE.clear()
    slow = SlowCart()
    monkeypatch.setattr(api, "get_cart", lambda: slow)
    monkeypatch.setattr(senso, "configured", lambda: True)          # Senso is on, and never answers in time
    monkeypatch.setattr(senso, "run_checks", lambda *a, **k: time.sleep(25))
    monkeypatch.setattr(api, "ensure_watcher", lambda: None)         # no background run in this test
    r, took = sign_request(env)
    RELEASE.set()
    assert r.status_code == 200, r.text
    assert took < 10, "the sign request took %.1f s" % took
    body = r.json()
    assert body["senso"] == "pending"
    modes = {c["mode"] for c in body["carts"]}
    assert modes == {"pending"}                                       # no store had answered: labelled, not hung
    assert all(c["cart_url"] is None for c in body["carts"])
    sig = env.engine.state["seal"]["signature"]
    assert sig["senso"]["status"] == "pending" and "still running" in sig["senso"]["label"]


def test_a_store_that_answers_after_the_seal_is_added_to_it(env, monkeypatch):
    RELEASE.clear()
    slow = SlowCart()
    monkeypatch.setattr(api, "get_cart", lambda: slow)
    monkeypatch.setattr(api, "CART_BUDGET_S", 0.5)
    r, took = sign_request(env)
    assert r.status_code == 200 and {c["mode"] for c in r.json()["carts"]} == {"pending"}
    RELEASE.set()
    deadline = time.time() + 5
    while time.time() < deadline and any(c["mode"] == "pending" for c in env.engine.state["seal"]["carts"]):
        time.sleep(0.1)
    assert all(c["cart_url"] for c in env.engine.state["seal"]["carts"])


def test_one_slow_store_does_not_hold_back_the_others(env, monkeypatch):
    RELEASE.clear()

    class OneSlow(FakeCart):
        def create_carts(self, picks):
            if picks[0]["store"].endswith("c.example"):
                RELEASE.wait(25)
            return super().create_carts(picks)
    monkeypatch.setattr(api, "get_cart", lambda: OneSlow())
    monkeypatch.setattr(api, "CART_BUDGET_S", 1.0)
    r, took = sign_request(env)
    RELEASE.set()
    modes = {c["store"]: c["mode"] for c in r.json()["carts"]}
    assert modes["fixture-store-c.example"] == "pending" and modes["fixture-store-a.example"] == "live"
    assert took < 5


def test_verdicts_for_the_current_hash_are_applied_without_a_run(env, monkeypatch):
    monkeypatch.setattr(senso, "configured", lambda: True)
    monkeypatch.setattr(api, "ensure_watcher", lambda: None)
    called = []
    monkeypatch.setattr(senso, "run_checks", lambda *a, **k: called.append(1))
    senso.set_checks([{"sentence": "Our order requires a grab bar to be bought through a cart.", "verdict": "conflict", "blocks": True}],
                     for_hash=env.engine.sheet_hash())
    r, took = sign_request(env)
    assert r.status_code == 409 and r.json()["error"] == "senso_blocked"
    assert not called and took < 2                                    # the request itself never starts a Senso run


def test_a_blocking_verdict_that_comes_back_within_the_wait_still_blocks(env, monkeypatch):
    monkeypatch.setattr(senso, "configured", lambda: True)
    monkeypatch.setattr(api, "ensure_watcher", lambda: None)
    h = env.engine.sheet_hash()
    timer = threading.Timer(1.0, lambda: senso.set_checks(
        [{"sentence": "x", "verdict": "conflict", "blocks": True}], for_hash=h))
    timer.start()
    r, took = sign_request(env)
    assert r.status_code == 409 and r.json()["error"] == "senso_blocked" and 0.8 < took < 4


def test_reset_asks_for_a_background_run(env):
    senso._kick.clear()
    env.client.post("/api/admin/reset")
    assert senso.kicked()
