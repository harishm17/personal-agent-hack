"""The independent review's holes in the approver path (H3, H6)."""
import json
import subprocess

from signoff.sign import persona

from .test_persona import FakePersona
from .standin import ROOT


def configured(monkeypatch):
    fake = FakePersona()
    monkeypatch.setattr(persona, "configured", lambda: True)
    monkeypatch.setattr(persona.config, "env", lambda name, default=None: "x")
    monkeypatch.setattr(persona.httpx, "post", fake.post)
    monkeypatch.setattr(persona.httpx, "get", fake.get)
    return fake


def signed_start(env):
    return env.client.post("/api/issuer/request", json=env.phone.request("persona_start"))


def test_an_open_call_cannot_start_an_inquiry(env, monkeypatch):
    """H3: POST /api/issuer/persona/start answered 200 from outside and replaced the inquiry."""
    fake = configured(monkeypatch)
    r = env.client.post("/api/issuer/persona/start")
    assert r.status_code in (401, 404, 405) and fake.posts == []
    assert persona.record()["inquiry_id"] is None


def test_an_unsigned_or_forged_start_is_refused(env, monkeypatch):
    fake = configured(monkeypatch)
    body = env.phone.request("persona_start")
    body["sig"] = "AAAA"
    assert env.client.post("/api/issuer/request", json=body).json()["error"] == "unsigned"
    assert fake.posts == []


def test_a_passed_check_cannot_be_undone_by_a_new_inquiry(env, monkeypatch):
    configured(monkeypatch)
    assert signed_start(env).status_code == 200
    env.client.post("/api/admin/persona/simulate", json={"action": "approve"})
    assert env.client.get("/api/issuer/persona/status").json()["verified"] is True
    inquiry = persona.record()["inquiry_id"]
    again = signed_start(env)
    assert again.status_code == 409 and again.json()["error"] == "identity_already_verified"
    assert persona.record()["verified"] is True and persona.record()["inquiry_id"] == inquiry


def test_the_sign_button_is_armed_only_for_the_sheet_she_saw():
    """H6: the second tap must not land on a sheet that changed after the first."""
    html = (ROOT / "web" / "phone" / "index.html").read_text()
    fn = html.split("/* arm:start */")[1].split("/* arm:end */")[0]
    def armed(*args):
        out = subprocess.run(["node", "-e", fn + "\nconsole.log(JSON.stringify(armed(%s)))" % ",".join(json.dumps(a) for a in args)],
                             capture_output=True, text=True, timeout=20)
        assert out.returncode == 0, out.stderr
        return json.loads(out.stdout)
    assert armed(1000, 5000, "h1", "h1") is True
    assert armed(1000, 5000, "h1", "h2") is False         # the sheet changed after the first tap
    assert armed(6000, 5000, "h1", "h1") is False         # four seconds passed
    assert armed(1000, 5000, None, "h1") is False
    assert "armedHash" in html and html.count("armedHash = null") >= 1   # loadState disarms the moment the hash changes
