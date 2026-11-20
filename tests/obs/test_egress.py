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


def test_sealed_values_follow_the_active_sheet_and_a_title_is_not_ours_to_seal(monkeypatch):
    from signoff.store import sheetctx
    monkeypatch.setattr(sheetctx, "active_id", lambda: "sheet2")
    hits = {(h["class"], h["match"]) for h in detect("1.28 gpf, 1.2 gpm, 1.8 gallons per minute, a 10-inch rough-in, 30 in alcove, Marco and Priya")}
    assert {("limit", "1.28 gpf"), ("limit", "1.2 gpm"), ("limit", "1.8 gpm"), ("home_measurement", "10 in"),
            ("home_measurement", "30 in"), ("person", "Marco"), ("person", "Priya")} <= hits
    assert detect("300 lb and Dana") == []  # sheet 1's values are not sealed on sheet 2
    title = "HOROW 8733-10 10-Inch Rough-In One-Piece Toilet"
    q = "Can an opened %s be returned, and how many business days does standard delivery take?" % title
    assert record("horow.com", "ask_business", {"ask": {"query": q}}, kind="store", block_on_hit=True)["blocked"]
    ok = record("horow.com", "ask_business", {"ask": {"query": q}}, kind="store", block_on_hit=True, mask=[title])
    assert not ok.get("blocked") and ok["sealed_hits"] == []
    assert record("horow.com", "ask_business", {"ask": {"query": "does it have a 10 in rough-in?"}}, kind="store",
                  block_on_hit=True, mask=[title])["blocked"]


def test_counts_come_from_the_saved_log_for_the_active_sheet(monkeypatch):
    from signoff.store import sheetctx
    monkeypatch.setattr(sheetctx, "active_id", lambda: "sheet1")
    record("carex.com", "search_catalog", {"q": "a"}, kind="store")
    monkeypatch.setattr(sheetctx, "active_id", lambda: "sheet2")
    record("horow.com", "search_catalog", {"q": "b"}, kind="store")
    record("horow.com", "search_catalog", {"q": "c"}, kind="store")
    import sys
    sys.modules["signoff.obs.egress"]._rows.clear()  # a restart: memory is gone, the file is not
    assert summary()["to_stores"] == 2 and summary(rows("sheet1"))["to_stores"] == 1 and len(rows("all")) == 3


def test_row_numbers_stay_unique_when_another_process_wrote_the_file():
    import sys
    mod = sys.modules["signoff.obs.egress"]
    a = record("x.com", "p", "a", kind="store")
    mod._rows.clear()  # a second process starts with an empty memory and appends to the same file
    b = record("x.com", "p", "b", kind="store")
    assert b["n"] == a["n"] + 1
