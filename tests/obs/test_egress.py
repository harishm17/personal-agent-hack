import json

import pytest

from signoff import obs
from signoff.obs import egress as _  # noqa: F401  (the function; the module is reached below)
from signoff.obs.egress import detect, kind_of, record, reset_for_tests, rows, summary
from signoff.store import ucp


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    import sys
    mod = sys.modules["signoff.obs.egress"]
    monkeypatch.setattr(mod, "LEDGER", tmp_path / "ledger.jsonl")
    reset_for_tests()


def test_sealed_values_are_found_with_their_units():
    hits = {(h["class"], h["match"]) for h in detect("Holds 300 lb, seat at 19 inches, tub 21.5 in wide; Dana said so")}
    assert ("limit", "300 lb") in hits and ("limit", "19 in") in hits
    assert ("home_measurement", "21.5 in") in hits and ("person", "Dana") in hits
    assert detect("shower chair, 30 lb bag, 190 in, 1300 lbs") == []  # other numbers and longer numbers are not ours


def test_store_payload_with_a_sealed_value_is_flagged_and_blocked():
    clean_row = record("carex.com", "search_catalog", {"catalog": {"query": "shower chair"}}, ["order"], block_on_hit=True)
    assert clean_row["sealed_hits"] == [] and not clean_row.get("blocked")
    bad = record("carex.com", "ask_business", {"ask": {"query": "does it hold 300 lb?"}}, ["product"], block_on_hit=True)
    assert bad["blocked"] and bad["sealed_hits"][0]["class"] == "limit" and "limit" in bad["fact_classes"]
    s = summary()
    assert s["messages"] == 2 and s["to_stores"] == 2 and s["limits_in_store_messages"] == 1 and s["blocked"] == 1


def test_rows_hold_hashes_not_payloads_and_non_store_recipients_are_not_blocked():
    r = record("anthropic:claude-sonnet-5-5", "read figures", "Weight Capacity: 300 lb.", ["store_text"], block_on_hit=True)
    assert r["kind"] == "model" and r["sealed_hits"] == [] and not r.get("blocked")
    assert "300" not in json.dumps({k: v for k, v in r.items() if k != "sealed_found_in_payload"})
    assert len(r["payload_sha256"]) == 64 and r["bytes"] == len("Weight Capacity: 300 lb.")
    assert kind_of("senso") == "sponsor service" and kind_of("vivehealth.com") == "store"


def test_store_client_refuses_to_send_a_sealed_value(monkeypatch):
    monkeypatch.setattr(ucp, "profile_url", lambda: "https://x/profile.json")
    monkeypatch.setattr(ucp.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sent")))
    monkeypatch.setenv("SIGNOFF_MODE", "live")
    with pytest.raises(RuntimeError, match="blocked"):
        ucp.ask_business("carex.com", "Is a 19 in height ok for Elena?")
    assert summary()["blocked"] == 1


def test_egress_never_raises():
    class Bad:
        def __str__(self):
            raise ValueError("no")
    assert obs.egress("x.com", "p", {"a": Bad()})["sealed_hits"] == []
