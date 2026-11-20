"""G23: the shopper asks, the approver decides. An ask is a record; only her signed request changes a limit."""
import copy

from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.sign import api, asks

from .conftest import _make_env
from .standin import FakeEngine


def ask(env, limit_id="L1.capacity", value=250, note="the chair I like is rated 250", **kw):
    return env.client.post("/api/shopper/ask-change", json={"limit_id": limit_id, "value": value, "note": note}, **kw)


def post(env, body):
    return env.client.post("/api/issuer/request", json=body)


def setup_function(_):
    asks.reset()


def limit_of(env, limit_id="L1.capacity"):
    for line in env.engine.state["sheet"]["lines"]:
        for l in line["limits"]:
            if l["id"] == limit_id:
                return l["bound"]["value"]


def test_an_ask_changes_no_limit_and_no_hash(env):
    before, hash_before = limit_of(env), env.engine.sheet_hash()
    r = ask(env)
    assert r.status_code == 200 and r.json()["ok"]
    a = r.json()["ask"]
    assert a["status"] == "pending" and a["from"] == before and a["to"] == 250 and a["by"] and a["limit_id"] == "L1.capacity"
    assert a["text"].endswith("holds at least 250 lb instead of 300 lb") and a["text"].startswith(a["by"] + " asks: ")
    assert limit_of(env) == before and env.engine.sheet_hash() == hash_before and env.engine.calls == []
    listed = env.client.get("/api/asks").json()
    assert listed["pending"] == 1 and listed["asks"][0]["id"] == a["id"] and listed["asks"][0]["outcome"].endswith("waiting")
    assert env.client.get("/api/issuer/status").json()["asks"][0]["id"] == a["id"]


def test_the_value_must_be_inside_the_limits_range(env):
    assert ask(env, value=100).json()["error"] == "out_of_range"
    assert ask(env, value=610).json()["error"] == "out_of_range"
    assert ask(env, value=260).json()["error"] == "off_step"
    assert ask(env, value="x").json()["error"] == "bad_value"
    assert ask(env, value=300).json()["error"] == "no_change"
    assert ask(env, limit_id="L1.tub").json()["error"] == "not_an_issuer_limit"
    assert ask(env, limit_id="nope").json()["error"] == "not_an_issuer_limit"
    assert env.client.get("/api/asks").json()["asks"] == []


def test_one_pending_ask_per_limit_a_new_one_replaces_it(env):
    first = ask(env, value=250).json()["ask"]
    second = ask(env, value=275).json()["ask"]
    rows = {a["id"]: a for a in env.client.get("/api/asks").json()["asks"]}
    assert rows[first["id"]]["status"] == "replaced" and rows[second["id"]]["status"] == "pending"
    assert env.client.get("/api/asks").json()["pending"] == 1


def test_accept_changes_the_limit_exactly_as_her_own_change_does(env):
    a = ask(env).json()["ask"]
    r = post(env, env.phone.request("set_limit", limit_id="L1.capacity", value=250, ask_id=a["id"]))
    assert r.status_code == 200, r.text
    kind, action = env.engine.calls[-1][:2]
    assert kind == "apply_issuer" and action["type"] == "set_limit" and action["limit_id"] == "L1.capacity" and action["value"] == 250
    assert action["ask_id"] == a["id"] and action["signer"]["name"] == "Dana"
    assert limit_of(env) == 250
    row = env.client.get("/api/asks").json()["asks"][0]
    assert row["status"] == "accepted" and row["settled_by"] == "Dana" and row["outcome"] == "Dana changed it to 250"
    again = post(env, env.phone.request("set_limit", limit_id="L1.capacity", value=250, ask_id=a["id"]))
    assert again.json()["error"] == "no_such_ask"                      # an ask settles once


def test_accept_must_carry_the_asked_limit_and_value(env):
    a = ask(env).json()["ask"]
    assert post(env, env.phone.request("set_limit", limit_id="L1.capacity", value=275, ask_id=a["id"])).json()["error"] == "ask_mismatch"
    assert post(env, env.phone.request("set_limit", limit_id="L2.height", value=20, ask_id=a["id"])).json()["error"] == "ask_mismatch"
    assert post(env, env.phone.request("set_limit", limit_id="L1.capacity", value=250, ask_id="ask-99")).json()["error"] == "no_such_ask"
    assert env.engine.calls == [] and limit_of(env) == 300


def test_a_decline_changes_nothing_and_says_who_declined(env):
    a = ask(env).json()["ask"]
    before, h = limit_of(env), env.engine.sheet_hash()
    r = post(env, env.phone.request("decline_ask", ask_id=a["id"]))
    assert r.status_code == 200 and r.json()["applied"] == "decline_ask"
    assert env.engine.calls == [] and limit_of(env) == before and env.engine.sheet_hash() == h
    row = env.client.get("/api/asks").json()["asks"][0]
    assert row["status"] == "declined" and row["settled_by"] == "Dana" and row["outcome"] == "Dana declined"
    assert env.client.get("/api/asks").json()["pending"] == 0


def test_a_decline_is_a_signed_request(env):
    a = ask(env).json()["ask"]
    body = env.phone.request("decline_ask", ask_id=a["id"])
    body["sig"] = "AAAA"
    assert post(env, body).json()["error"] == "unsigned"
    assert env.client.get("/api/asks").json()["pending"] == 1
    assert post(env, {"payload": '{"type":"decline_ask","ask_id":"%s"}' % a["id"], "sig": "x", "key_id": "this-screen"}).status_code == 401


def test_her_own_change_settles_a_waiting_ask(env):
    ask(env, value=250)
    assert post(env, env.phone.request("set_limit", limit_id="L1.capacity", value=350)).status_code == 200
    row = env.client.get("/api/asks").json()["asks"][0]
    assert row["status"] == "changed" and row["changed_to"] == 350 and row["outcome"] == "Dana changed it to 350"


def test_after_sealing_an_ask_is_refused(env):
    assert post(env, env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())).status_code == 200
    r = ask(env)
    assert r.status_code == 409 and r.json()["error"] == "already_signed"
    assert env.client.get("/api/asks").json()["asks"] == []


def test_an_ask_from_outside_the_laptop_is_refused_by_the_guard(env):
    from signoff.app import admin_guard
    app = FastAPI()
    app.middleware("http")(admin_guard)
    app.include_router(api.router)
    client = TestClient(app)
    through_tunnel = client.post("/api/shopper/ask-change", json={"limit_id": "L1.capacity", "value": 250}, headers={"cf-connecting-ip": "1.2.3.4"})
    assert through_tunnel.status_code == 403 and through_tunnel.json()["error"] == "local_only"
    assert asks.listing(env.engine.state)["asks"] == []


def test_a_reset_starts_with_no_asks(env):
    ask(env)
    env.client.post("/api/admin/reset")
    assert env.client.get("/api/asks").json()["asks"] == []
