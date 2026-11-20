import json
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.engine import api, receipts, state

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture(autouse=True)
def fixture_sheet(monkeypatch, tmp_path):
    monkeypatch.setattr(state, "DATA", tmp_path)
    monkeypatch.setattr(state, "_load_pool", lambda: (json.loads((ROOT / "fixtures" / "pool.json").read_text()),
                                                      json.loads((ROOT / "fixtures" / "store_answers.json").read_text())))
    monkeypatch.setattr(state, "_record", lambda s: None)
    monkeypatch.setattr(receipts, "FOLDER", tmp_path / "receipts")
    monkeypatch.setenv("SIGNOFF_RECEIPTS", "file")
    state.reset()
    yield
    state._s["loaded"] = False


def types():
    return [r["type"] for r in receipts.chain()["receipts"]]


def test_every_change_the_engine_applies_leaves_a_receipt_and_the_chain_verifies():
    assert types() == ["chain_started"]
    signer = {"key_id": "k1", "name": "Dana"}
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425, "seq": 1, "signer": signer})
    state.apply_issuer({"type": "strike", "line_id": "L2", "product_key": "fixture d", "reason": "x", "signer": signer})
    state.apply_issuer({"type": "unstrike", "line_id": "L2", "product_key": "fixture d", "signer": signer})
    state.set_shopper_fact("toilet_rim_height", 14.5)
    state.mark_signed({"name": "Dana", "signer": signer, "at": "2026-11-20T14:00:00-08:00", "sheet_hash": state.sheet_hash()},
                      [{"store": "fixture-store-a.example", "cart_id": "c1", "cart_url": "u", "total_cents": 1, "mode": "fixture"}])
    assert types() == ["chain_started", "limit_set", "strike", "unstrike", "shopper_fact", "signed", "carts_created"]
    held = receipts.chain()["receipts"]
    assert [r["n"] for r in held] == list(range(1, 8)) and held[0]["prev_hash"] == receipts.ZERO
    assert all(set(r) >= {"n", "at", "type", "actor", "key_id", "body_hash", "prev_hash", "hash"} for r in held)
    assert all(b["prev_hash"] == a["hash"] for a, b in zip(held, held[1:]))
    limit = held[1]
    assert (limit["actor"], limit["key_id"]) == ("issuer", "k1") and limit["detail"] == {
        "limit_id": "L2.capacity", "from": 300, "to": 425, "unit": "lb"}
    assert held[4]["actor"] == "shopper" and held[4]["key_id"] is None
    assert receipts.verify() == {"count": 7, "verified": True, "first_bad": None, "checked": "file and memory",
                                 "chain": receipts.chain()["chain"]}
    s = state.get_state()["receipts"]
    assert s["count"] == 7 and s["verified"] is True and s["last_hash"] == held[-1]["hash"]


def test_a_refused_request_is_receipted_too_and_a_reset_starts_a_new_chain_that_names_the_old_one():
    receipts.signed_request('{"type":"set_limit","limit_id":"L2.capacity","value":9000,"seq":4}', "k1", False,
                            "L2.capacity must be between 200 and 600")
    receipts.signed_request({"type": "strike", "line_id": "L2", "product_key": "fixture d", "seq": 5}, "k1", True)
    held = receipts.chain()["receipts"]
    assert [r["type"] for r in held] == ["chain_started", "request_refused", "request_accepted"]
    assert held[1]["detail"]["refused_because"].startswith("L2.capacity must be") and held[1]["detail"]["value"] == 9000
    old_chain, last = receipts.chain()["chain"], held[-1]["hash"]
    state.reset()
    new = receipts.chain()
    assert new["chain"] != old_chain and len(new["receipts"]) == 1
    assert new["receipts"][0]["detail"]["previous"] == {"chain": old_chain, "last_hash": last, "count": 3}


def test_an_edit_to_any_receipt_on_disk_is_found():
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 300})
    state.set_shopper_fact("toilet_rim_height", 14.5)
    path = ROOT / receipts.chain()["file"] if not pathlib.Path(receipts.chain()["file"]).is_absolute() else pathlib.Path(receipts.chain()["file"])
    lines = path.read_text().splitlines()
    assert len(lines) == 4 and receipts.verify()["verified"] is True
    forged = json.loads(lines[1])
    forged["detail"]["to"] = 250  # someone rewrites what the limit was set to
    path.write_text("\n".join([lines[0], json.dumps(forged, sort_keys=True, separators=(",", ":"))] + lines[2:]) + "\n")
    assert receipts.verify()["verified"] is False and receipts.verify()["first_bad"] == 2
    forged["hash"] = receipts.hash_of(forged)  # they fix that receipt's own hash: the next link gives it away
    path.write_text("\n".join([lines[0], json.dumps(forged, sort_keys=True, separators=(",", ":"))] + lines[2:]) + "\n")
    assert receipts.verify()["first_bad"] == 3
    path.write_text("\n".join(lines[:3]) + "\n")  # they drop the last receipt
    assert receipts.verify()["verified"] is False and receipts.verify()["first_bad"] == 4


def test_routes():
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    listed = client.get("/api/receipts").json()
    assert [r["type"] for r in listed["receipts"]] == ["chain_started", "limit_set"]  # newest last
    checked = client.get("/api/receipts/verify").json()
    assert (checked["count"], checked["verified"], checked["first_bad"]) == (2, True, None)
    assert client.get("/api/state").json()["receipts"]["count"] == 2


def test_a_receipt_never_breaks_a_change(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(receipts, "_append", broken)
    s = state.apply_issuer({"type": "set_limit", "limit_id": "L2.capacity", "value": 425})
    assert next(l for l in s["lines"] if l["line_id"] == "L2")["pick"] == "L2:fixture-store-c.example:fx-D"
