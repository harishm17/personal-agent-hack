from signoff.sign import persona


def start(env):
    """The phone starts the identity check with a signed request (H3), not an open route."""
    return env.client.post("/api/issuer/request", json=env.phone.request("persona_start"))


def test_without_keys_the_flow_says_identity_not_checked(env):
    started = start(env).json()
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
    started = start(env).json()
    assert started["inquiry_id"] == "inq_123" and started["link"].endswith("inquiry-id=inq_123")
    assert started["verified"] is False
    status = env.client.get("/api/issuer/persona/status").json()
    assert status["verified"] is True and "sandbox" in status["label"]
    env.client.post("/api/admin/reset")
    assert env.client.get("/api/issuer/persona/status").json()["inquiry_id"] is None


class FakePersona:
    """Persona's sandbox backend: create an inquiry, simulate actions, read the status back."""

    def __init__(self):
        self.status, self.posts = "created", []

    def post(self, url, headers=None, json=None, timeout=None):
        self.posts.append(url)
        if url.endswith("/inquiries"):
            self.status = "created"
        else:
            self.status = {"approve_inquiry": "approved", "decline_inquiry": "declined"}[json["meta"]["simulate-actions"][0]["type"]]
        outer = self
        return type("R", (), {"status_code": 200, "json": lambda s: {"data": {"id": "inq_9", "attributes": {"status": outer.status}}}})()

    def get(self, url, headers=None, timeout=None):
        outer = self
        return type("R", (), {"status_code": 200, "json": lambda s: {"data": {"id": "inq_9", "attributes": {"status": outer.status}}}})()


def test_identity_gate_refuses_then_approves_the_same_signature(env, monkeypatch):
    monkeypatch.setenv("PERSONA_REQUIRED", "1")
    monkeypatch.setattr(persona, "configured", lambda: True)
    monkeypatch.setattr(persona.config, "env", lambda name, default=None: __import__("os").environ.get(name, "x"))
    fake = FakePersona()
    monkeypatch.setattr(persona.httpx, "post", fake.post)
    monkeypatch.setattr(persona.httpx, "get", fake.get)
    seen = []
    from signoff.sign import api
    monkeypatch.setattr(api, "receipt", lambda *a, **k: seen.append(a))
    body = [env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())]
    post = lambda: env.client.post("/api/issuer/request", json=body[0])

    r = post()                                                    # no inquiry yet
    assert r.status_code == 403 and r.json()["error"] == "identity_not_verified" and r.json()["detail"] == "identity not verified"
    started = start(env).json()
    assert started["inquiry_id"] == "inq_9" and started["sandbox"] is True
    body[0] = env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash())   # the phone signs a new request after its own signed start
    assert post().json()["error"] == "identity_not_verified"      # created, not approved
    declined = env.client.post("/api/admin/persona/simulate", json={"action": "decline"}).json()
    assert declined["status"] == "declined" and declined["simulated"] and not declined["verified"]
    assert post().json()["error"] == "identity_not_verified" and env.cart.calls == []
    approved = env.client.post("/api/admin/persona/simulate", json={"action": "approve"}).json()
    assert approved["status"] == "approved" and approved["verified"]

    ok = post()                                                   # the very same signed request goes through
    assert ok.status_code == 200, ok.text
    sig = env.engine.state["seal"]["signature"]
    assert sig["persona"]["inquiry_id"] == "inq_9" and sig["persona"]["status"] == "approved" and sig["persona"]["sandbox"] is True
    assert "sandbox" in sig["persona"]["label"]
    assert [a[1] for a in seen].count(False) == 3 and seen[-1][1] is True   # every refusal and the signature left a receipt


def test_simulate_needs_a_started_inquiry(env):
    r = env.client.post("/api/admin/persona/simulate", json={"action": "approve"}).json()
    assert r["simulated"] is False


def test_production_key_is_never_read():
    import pathlib
    for f in pathlib.Path("signoff/sign").glob("*.py"):
        assert "PERSONA_PRODUCTION" not in f.read_text()


def test_the_identity_gate_is_on_unless_explicitly_switched_off(env, monkeypatch):
    monkeypatch.delenv("PERSONA_REQUIRED", raising=False)
    monkeypatch.setattr(persona.config, "env", lambda name, default=None: None)
    from signoff.sign import api
    assert api.identity_required() is True
    assert env.client.get("/api/issuer/status").json()["identity_required"] is True
    r = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash()))
    assert r.status_code == 403 and r.json()["detail"] == "identity not verified"
    monkeypatch.setattr(api.config, "env", lambda name, default=None: "0" if name == "PERSONA_REQUIRED" else None)
    assert api.identity_required() is False
