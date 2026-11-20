from signoff.sign import persona


def test_without_keys_the_flow_says_identity_not_checked(env):
    started = env.client.post("/api/issuer/persona/start").json()
    assert started["status"] == "not_checked" and started["label"] == "identity not checked" and started["link"] is None
    status = env.client.get("/api/issuer/persona/status").json()
    assert status["inquiry_id"] is None and status["verified"] is False and status["sandbox"] is True


def test_with_keys_inquiry_is_created_and_read(env, monkeypatch):
    class R:
        def __init__(self, status): self.status_code, self._s = 200, status
        def json(self): return {"data": {"id": "inq_123", "attributes": {"status": self._s}}}
    monkeypatch.setattr(persona, "configured", lambda: True)
    monkeypatch.setattr(persona.config, "env", lambda name, default=None: "x")
    monkeypatch.setattr(persona.httpx, "post", lambda *a, **k: R("created"))
    monkeypatch.setattr(persona.httpx, "get", lambda *a, **k: R("approved"))
    started = env.client.post("/api/issuer/persona/start").json()
    assert started["inquiry_id"] == "inq_123" and started["link"].endswith("inquiry-id=inq_123")
    assert started["verified"] is False
    status = env.client.get("/api/issuer/persona/status").json()
    assert status["verified"] is True and "sandbox" in status["label"]
    env.client.post("/api/admin/reset")
    assert env.client.get("/api/issuer/persona/status").json()["inquiry_id"] is None


def test_signing_can_require_a_passed_check(env, monkeypatch):
    monkeypatch.setenv("PERSONA_REQUIRED", "1")
    body = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())
    r = env.client.post("/api/issuer/request", json=body)
    assert r.status_code == 403 and r.json()["error"] == "identity_needed" and env.cart.calls == []
    monkeypatch.setattr(persona, "status", lambda: {"verified": True})
    ok = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash()))
    assert ok.status_code == 200
