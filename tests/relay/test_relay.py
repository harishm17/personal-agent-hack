import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff import relay
from signoff.relay import api, core


@pytest.fixture(autouse=True)
def clean():
    core._session, core._result = None, None
    yield
    core._session, core._result = None, None


def test_status_is_none_until_a_claim_exists():
    assert relay.status() is None


def test_complete_without_a_session_says_so():
    assert core.complete() == {"ok": False, "error": "no session started"}


def test_pending_claim_is_not_a_result(monkeypatch):
    calls = []

    def fake(payload, timeout=60):
        calls.append(payload["op"])
        if payload["op"] == "create":
            return {"ok": True, "relayToken": "t", "relaySecret": "s", "relaySessionAccessToken": "a"}
        if payload["op"] == "issue":
            return {"ok": True, "privacyPassToken": "p"}
        return {"ok": False, "status": 403, "message": "claim not yet available"}
    monkeypatch.setattr(core, "_helper", fake)
    started = core.start()
    assert started["ok"] and started["sandbox"] is True and "relay-session-access-token=a" in started["hosted_url"]
    assert "relaySecret" not in str(started) and "relay_secret" not in str(started)
    assert core.complete() == {"ok": True, "pending": True}
    assert relay.status() is None


def test_passed_claim_is_stored_and_labelled_sandbox(monkeypatch):
    def fake(payload, timeout=60):
        return {"create": {"ok": True, "relayToken": "t", "relaySecret": "s", "relaySessionAccessToken": "a"},
                "issue": {"ok": True, "privacyPassToken": "p"},
                "claim": {"ok": True, "tokenConsumed": True, "claimPayload":
                          '{"claim_type":"live_human_presence","claim_result":"passed","methodology":[{"method":"live_selfie","result":"passed"}]}'}}[payload["op"]]
    monkeypatch.setattr(core, "_helper", fake)
    core.start()
    done = core.complete()
    assert done["result"] == "passed" and done["sandbox"] is True
    s = relay.status()
    assert set(s) == {"claim_type", "result", "sandbox", "at"} and s["sandbox"] is True


def test_routes(monkeypatch):
    app = FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    body = c.get("/api/issuer/relay/status").json()
    assert body["sandbox"] is True and body["result"] is None


@pytest.mark.live
def test_full_pass_against_persona_sandbox():
    started = core.start()
    assert started["ok"], started
    done = core.complete()
    assert done["ok"] and done["result"] == "passed" and done["sandbox"] is True, done
    assert relay.status()["claim_type"] == "live_human_presence"
