"""Sheet 3 (a teacher's class supply list): sentences are the order document's own words; nothing assumes another sheet."""
import re

from signoff.sign import senso

from .conftest import _make_env
from .sheet3_state import build
from .standin import ROOT, FakeEngine

ORDER3 = (ROOT / "sheets" / "sheet3_order.txt").read_text()


def test_every_sentence_is_in_the_order_document_word_for_word():
    rows = senso.sentences_for(build())
    assert {r["kind"] for r in rows} == {"limit", "order"} and len(rows) == 8
    for r in rows:
        assert r["sentence"] in ORDER3, r["sentence"]
    assert "Our order requires headphones for computer time." in {r["sentence"] for r in rows}      # no "a headphones"
    assert "Our order requires a box of crayons to have exactly 24 crayons." in {r["sentence"] for r in rows}


def test_a_value_the_issuer_has_moved_is_written_into_the_orders_own_sentence():
    st = build()
    for line in st["sheet"]["lines"]:
        for l in line["limits"]:
            if l["id"] == "C1.volume":
                l["bound"]["value"] = 80
                l["from_order"] = {"value": 85, "matches": False, "quote": "q"}
    row = next(r for r in senso.sentences_for(st) if "play no louder" in r["sentence"])
    assert row["sentence"] == "Our order requires the headphones to play no louder than 80 decibels." and row["moved_from_order"] is True


def test_the_documents_for_sheet_3_are_its_own_order_with_its_own_key():
    docs = senso.documents("sheet3")
    assert docs[0]["key"] == "order:sheet3" and docs[0]["text"] == ORDER3
    assert "handout" not in {d["key"] for d in docs}


def test_the_phone_and_the_code_read_names_roles_and_units_from_the_sheet(monkeypatch):
    html = (ROOT / "web" / "phone" / "index.html").read_text()
    banned = re.compile(r"Ms\. Alvarez|\bDev\b|teacher|room parent|headphones|crayons|(?-i:\bdB\b)", re.I)
    assert not banned.search(html)
    for f in ("api.py", "verify.py", "persona.py", "carts.py"):
        assert not banned.search((ROOT / "signoff" / "sign" / f).read_text()), f


def test_a_limit_move_a_signature_and_the_carts_on_sheet_3(monkeypatch):
    env = _make_env(monkeypatch, FakeEngine(build), "sheet3")
    post = lambda body: env.client.post("/api/issuer/request", json=body)
    assert post(env.phone.request("set_limit", limit_id="C1.volume", value=80)).status_code == 200
    assert post(env.phone.request("set_limit", limit_id="C1.volume", value=85.5)).json()["error"] == "off_step"      # a step of 1 dB
    assert post(env.phone.request("set_limit", limit_id="C2.count", value=30)).json()["error"] == "off_step"         # a step of 8
    assert post(env.phone.request("set_limit", limit_id="C2.count", value=32)).status_code == 200
    r = post(env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash()))
    assert r.status_code == 200, r.text
    assert 3 <= len({c["store"] for c in r.json()["carts"]}) <= 5


def test_the_phones_wording_can_come_from_the_sheet_and_defaults_to_today_s_words():
    html = (ROOT / "web" / "phone" / "index.html").read_text()
    assert 'state.sheet.vocab' in html and 'V("limit"' in html or 'V("order"' in html
    for old in ('"from the order"', '"changed from the order"', 'Adjust a limit</button>'):
        assert old not in html, old                       # every such phrase now goes through the sheet's vocabulary
