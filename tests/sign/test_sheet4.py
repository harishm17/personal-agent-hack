"""Sheet 4, "Home after surgery, short": the lead example. Three items with sheet 1's line and limit ids and its own order."""
from signoff.sign import senso

from .conftest import _make_env
from .sheet4_state import build
from .standin import ROOT, FakeEngine

ORDER4 = (ROOT / "sheets" / "sheet4_order.txt").read_text()


def test_sentences_are_the_order_documents_own_words_with_the_value_set_now():
    rows = senso.sentences_for(build())
    assert {r["kind"] for r in rows} == {"limit", "order"} and len(rows) == 3 + 4     # 3 items, the four limits the issuer sets
    for r in rows:
        assert r["sentence"] in ORDER4, r["sentence"]
    assert "Our order requires a shower chair or transfer bench for the bathroom." in {r["sentence"] for r in rows}
    st = build()
    for line in st["sheet"]["lines"]:
        for l in line["limits"]:
            if l["id"] == "L1.capacity":
                l["bound"]["value"] = 350
                l["from_order"] = {"value": 300, "matches": False, "quote": "q"}
    moved = [r for r in senso.sentences_for(st) if r["moved_from_order"]]
    assert [r["sentence"] for r in moved] == ["Our order requires the shower chair to hold at least 350 lb."]


def test_the_documents_for_sheet_4_are_its_own_order():
    docs = senso.documents("sheet4")
    assert docs[0]["key"] == "order:sheet4" and docs[0]["text"] == ORDER4
    assert "handout" not in {d["key"] for d in docs}


def test_a_weight_limit_move_changes_the_pick_and_the_therapist_signs(monkeypatch):
    env = _make_env(monkeypatch, FakeEngine(build), "sheet4")
    post = lambda body: env.client.post("/api/issuer/request", json=body)
    assert post(env.phone.request("set_limit", limit_id="L1.capacity", value=350)).status_code == 200
    assert post(env.phone.request("set_limit", limit_id="L1.capacity", value=310)).json()["error"] == "off_step"      # steps of 25
    assert post(env.phone.request("set_limit", limit_id="L1.tub", value=20)).json()["error"] == "not_an_issuer_limit"  # Elena's measurement
    assert post(env.phone.request("set_limit", limit_id="L5.length", value=20)).status_code == 200
    r = post(env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash()))
    assert r.status_code == 200, r.text
    assert {c["store"] for c in r.json()["carts"]} <= {"carex.com", "vivehealth.com", "parentgiving.com"}
