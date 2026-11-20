"""Nothing in SIGN assumes sheet 1: the plumber's fixture list (four stores, lines T1 to T4, an `==` limit, units gpf
and gpm) goes through the same sentences, signing, carts and seal."""
import pathlib
import re

from signoff.sign import api, senso

from .standin import ROOT
from .sheet2_state import build

ORDER2 = (ROOT / "sheets" / "sheet2_order.txt").read_text()


def test_every_sentence_for_sheet_2_is_in_its_order_document_word_for_word():
    rows = senso.sentences_for(build())
    assert {r["kind"] for r in rows} == {"limit", "order"} and len(rows) == 7
    for r in rows:
        assert r["sentence"] in ORDER2, r["sentence"]


def test_sheet_2_documents_are_its_own_order_with_its_own_key():
    docs = senso.documents("sheet2")
    assert [d["key"] for d in docs if not d["key"].startswith("store:")] == ["order:sheet2"]
    assert docs[0]["text"] == ORDER2
    assert "handout" not in {d["key"] for d in docs}
    sheet1 = {d["key"] for d in senso.documents("sheet1")}
    assert {"order", "handout"} <= sheet1                              # sheet 1's documents are as they were


def test_only_issuer_limits_get_a_sentence_and_the_equals_limit_is_left_to_the_home():
    sentences = " ".join(r["sentence"] for r in senso.sentences_for(build()))
    assert "flush volume" in sentences and "flow rate" in sentences
    assert "rough-in" not in sentences and "alcove" not in sentences   # bounded by the house, not by the order


def test_the_code_and_the_phone_assume_no_sheet_1_names_roles_or_ids():
    banned = re.compile(r"therapist|\bDana\b|\bElena\b|\bL[1-6]\b|hip surgery|commode|shower chair|\bshe\b|\bhe cannot", re.I)
    for f in ("web/phone/index.html", "signoff/sign/api.py", "signoff/sign/verify.py", "signoff/sign/persona.py"):
        text = (ROOT / f).read_text()
        assert not banned.search(text), "%s: %s" % (f, banned.search(text).group(0))


def test_a_limit_move_a_strike_and_a_signature_work_on_four_stores(env2):
    post = lambda body: env2.client.post("/api/issuer/request", json=body)
    # the flush limit has a step of 0.01 and a unit the sheet 1 never had
    assert post(env2.phone.request("set_limit", limit_id="T1.flush", value=1.1)).status_code == 200
    assert env2.engine.calls[-1][1]["value"] == 1.1
    assert post(env2.phone.request("set_limit", limit_id="T1.flush", value=1.105)).json()["error"] == "off_step"
    assert post(env2.phone.request("set_limit", limit_id="T1.rough_in", value=12)).json()["error"] == "not_an_issuer_limit"   # the house's measurement
    assert post(env2.phone.request("set_limit", limit_id="L1.capacity", value=300)).json()["error"] == "not_an_issuer_limit"  # sheet 1's id means nothing here
    line = next(l for l in env2.engine.state["lines"] if l["line_id"] == "T2")
    key = next(c["product"]["product_key"] for c in line["candidates"] if c["picked"])
    assert post(env2.phone.request("strike", line_id="T2", product_key=key, reason="not suitable")).status_code == 200
    r = post(env2.phone.request("sign_sheet", sheet_hash=env2.engine.sheet_hash()))
    assert r.status_code == 200, r.text
    stores = {c["store"] for c in r.json()["carts"]}
    assert stores == {p["store"] for call in env2.cart.calls for p in call} and 2 <= len(stores) <= 4
    sig = env2.engine.state["seal"]["signature"]
    assert sig["name"] == "Dana (self-declared)" or sig["name"].endswith("(self-declared)")


def test_the_seal_and_the_comparisons_cover_four_stores(env2, monkeypatch):
    stores = ["swissmadison.com", "horow.com", "deervalleybath.com", "kingstonbrass.com"]
    picks = [{"store": s, "variant_id": "gid://v/%d" % i, "quantity": 1, "price_cents": 1000 * (i + 1)} for i, s in enumerate(stores)]
    carts = [{"store": s, "cart_id": "c", "cart_url": "https://x/%s" % s, "mode": "live", "total_cents": 1000 * (i + 1),
              "lines": [{"variant_id": "gid://v/%d" % i, "quantity": 1, "unit_price_cents": 1000 * (i + 1)}]} for i, s in enumerate(stores)]
    carts[2]["total_cents"] = 3300                                     # one store's total moved
    out = api._check_lines(api._check_totals(carts, picks, env2.engine.state), picks)
    assert [bool(c.get("total_differs")) for c in out] == [False, False, True, False]
    assert "signed $30.00, store $33.00" in out[2]["note"] and all(c["lines_checked"] for c in out)
