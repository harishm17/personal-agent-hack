"""Receipts and the outbound ledger: enrolment, Persona's result, Senso's run and every request to Senso and Persona."""
from signoff.sign import api, audit, persona, senso

from .conftest import Phone
from .test_persona import FakePersona


class Log:
    def __init__(self, monkeypatch):
        self.receipts, self.egress = [], []
        monkeypatch.setattr(audit, "receipt", lambda kind, actor, key_id=None, body=None, detail=None: self.receipts.append((kind, actor, key_id, detail)))
        monkeypatch.setattr(audit, "egress", lambda recipient, purpose, payload=None, fact_classes=None: self.egress.append((recipient, purpose, payload, fact_classes)))


def test_enrolment_and_a_refused_enrolment_each_leave_a_receipt(env, monkeypatch):
    log = Log(monkeypatch)
    env.client.post("/api/admin/reset")
    assert env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Dana", "code": "wrong"}).status_code == 403
    ok = env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Dana", "code": api.keystore.code})
    assert ok.status_code == 200
    assert [r[0] for r in log.receipts] == ["enrolment_refused", "enrolled"]
    assert log.receipts[0][3] == {"refused_because": "bad_code"} and log.receipts[1][2] == ok.json()["key_id"]


def test_persona_requests_are_in_the_ledger_and_each_new_result_is_a_receipt(env, monkeypatch):
    log = Log(monkeypatch)
    monkeypatch.setattr(persona, "configured", lambda: True)
    monkeypatch.setattr(persona.config, "env", lambda name, default=None: "x")
    fake = FakePersona()
    monkeypatch.setattr(persona.httpx, "post", fake.post)
    monkeypatch.setattr(persona.httpx, "get", fake.get)
    env.client.post("/api/issuer/request", json=env.phone.request("persona_start"))
    env.client.get("/api/issuer/persona/status")        # unchanged: no second receipt
    env.client.post("/api/admin/persona/simulate", json={"action": "approve"})
    assert [e[0] for e in log.egress] == ["persona"] * 4
    assert [r[0] for r in log.receipts] == ["persona_status", "persona_status"]
    assert log.receipts[0][3]["status"] == "created" and log.receipts[1][3]["status"] == "approved" and log.receipts[1][3]["sandbox"] is True


def test_senso_requests_are_in_the_ledger_and_a_run_is_a_receipt(monkeypatch):
    log = Log(monkeypatch)
    monkeypatch.setattr(senso, "configured", lambda: True)

    class Client:
        def post(self, url, json):
            class R:
                status_code = 200
                def json(s):
                    return {"status": "completed", "eval_run_id": "r", "claims": [{"claim_text": "c", "verdict": "verified", "quote": "q", "evidence": []}]}
            return R()
    from .sheet2_state import build
    state = build()
    monkeypatch.setattr(senso.httpx, "Client", lambda *a, **k: type("C", (), {"__enter__": lambda s: Client(), "__exit__": lambda s, *a: None})())
    out = senso.run_checks(state, "h1")
    assert out["for_hash"] == "h1"
    assert len(log.egress) == 7 and {e[0] for e in log.egress} == {"senso"}
    assert all(e[2].startswith("Our order requires") for e in log.egress)
    receipt = [r for r in log.receipts if r[0] == "senso_checked"]
    assert len(receipt) == 1 and receipt[0][3]["sentences"] == 7 and receipt[0][3]["verdicts"] == {"verified": 7}


def test_the_real_chain_takes_the_receipts(env, monkeypatch):
    monkeypatch.setenv("SIGNOFF_RECEIPTS", "memory")
    from signoff.engine import receipts
    receipts.start("test")
    before = receipts.summary()["count"]
    env.client.post("/api/admin/reset")
    env.client.post("/api/issuer/enroll", json={"public_key_jwk": Phone().jwk, "name": "Dana", "code": api.keystore.code})
    chain = receipts.chain()
    assert receipts.summary()["count"] > before
    assert "enrolled" in [r["type"] for r in chain["receipts"]] and receipts.verify()["verified"] is True
