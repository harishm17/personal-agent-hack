import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff import memory
from signoff.engine import receipts
from signoff.memory import api, sources, store

from .conftest import signed_strike


def _source(receipt):
    chain = receipts.chain()
    return {"type": "receipt", "chain": chain["chain"], "n": receipt["n"], "hash": receipt["hash"]}


def _measure(value, fact="tub_inside_width", was=21.5):
    return receipts.append("shopper_fact", "shopper", None, {"fact_id": fact, "value": value},
                           {"fact_id": fact, "from": was, "to": value, "unit": "in"})


def test_a_made_up_memory_is_refused(records):
    receipts.start("sheet sheet4")
    made_up = {"owner": "shopper", "kind": "home_measurement", "key": "tub_inside_width", "value": {"value": 29.0, "unit": "in"},
               "text": "The tub is 29 in wide."}
    for source in (None, {"type": "model", "text": "the page says the tub is 29 in"},
                   {"type": "receipt", "chain": "20260101T000000.000000", "n": 2, "hash": "0" * 64},
                   {"type": "receipt", "chain": receipts.chain()["chain"], "n": 7, "hash": "f" * 64},
                   {"type": "file", "file": "data/store_answers/nobody.example.json", "index": 0}):
        with pytest.raises(memory.Refused) as refused:
            memory.write(dict(made_up, source=source))
        assert refused.value.code in ("no_source", "no_such_record")
    assert store.mirror_rows() == []


def test_a_memory_that_says_more_than_its_record_is_refused(records):
    receipts.start("sheet sheet4")
    receipt = _measure(22.5)
    proved = sources.prove(_source(receipt))[0]
    with pytest.raises(memory.Refused) as refused:
        memory.write(dict(proved, value=dict(proved["value"], value=29.0)))
    assert refused.value.code == "record_says_otherwise"
    with pytest.raises(memory.Refused):
        memory.write(dict(proved, owner="issuer"))
    assert memory.write(proved, database=False)["value"]["value"] == 22.5
    assert [r["id"] for r in store.mirror_rows()] == [proved["id"]]


def test_an_issuer_memory_without_a_signed_request_is_refused(records, product):
    receipts.start("sheet sheet4")
    bare = receipts.append("strike", "issuer", "key0000000000001", {"type": "strike", **product},
                           {"line_id": product["line_id"], "product_key": product["product_key"], "reason": "too flimsy"})
    no_key = receipts.append("strike", "issuer", None, {"type": "strike", **product},
                             {"line_id": product["line_id"], "product_key": product["product_key"], "reason": "too flimsy"})
    refused_request = receipts.append("strike", "issuer", "key0000000000002", {"type": "strike", **product},
                                      {"line_id": product["line_id"], "product_key": product["product_key"]})
    receipts.signed_request(json.dumps({"type": "strike", **product}), "key0000000000002", False, "bad signature")
    for receipt in (bare, no_key, refused_request):
        with pytest.raises(memory.Refused) as refused:
            memory.write({"owner": "issuer", "kind": "strike", "key": product["product_key"], "source": _source(receipt)})
        assert refused.value.code == "no_signed_request"
    derived = memory.sync()
    assert [m for m in derived["memories"] if m["kind"] == "strike"] == []
    assert [r["code"] for r in derived["not_memories"]] == ["no_signed_request"] * 3


def test_a_signed_strike_is_remembered_with_its_reason_and_its_two_receipts(records, product):
    receipts.start("sheet sheet4")
    change = signed_strike(product, "the suction cup lets go on tile")
    row = memory.write({"owner": "issuer", "kind": "strike", "key": product["product_key"], "source": _source(change)},
                       database=False)
    assert row["owner"] == "issuer" and row["owner_name"] == "Dana" and row["sheet_id"] == "sheet4"
    assert row["value"]["reason"] == "the suction cup lets go on tile" and row["value"]["struck"] is True
    assert row["source"]["signed_request"]["n"] == change["n"] + 1 and row["source"]["key_id"] == "key0000000000001"
    assert product["title"] in row["text"] and "suction cup" in row["text"]


def test_nothing_is_remembered_from_a_chain_that_was_edited(records):
    receipts.start("sheet sheet4")
    receipt = _measure(22.5)
    file = receipts.chain()["file"]
    path = records / "receipts" / file.split("/")[-1]
    path.write_text(path.read_text().replace('"to":22.5', '"to":29.0'))
    with pytest.raises(memory.Refused) as refused:
        sources.prove(_source(receipt))
    assert refused.value.code == "chain_broken"
    derived = memory.sync()
    assert [m for m in derived["memories"] if m["kind"] == "home_measurement"] == []
    assert [r["code"] for r in derived["not_memories"]] == ["chain_broken"]


def test_a_new_run_recalls_the_measurement_the_strike_and_the_stores_answers(records, sheet, product):
    receipts.start("sheet sheet4")
    _measure(22.0)
    last = _measure(22.5, was=22.0)
    signed_strike(product, "the suction cup lets go on tile")
    receipts.start("reset")  # a new chain; the one before it stays on disk
    recalled = memory.recall(sheet)
    assert recalled["error"] is None
    [fact] = recalled["facts"]
    assert (fact["fact_id"], fact["value"], fact["measured_by"], fact["measured_at"]) == ("tub_inside_width", 22.5, "Elena", last["at"])
    assert fact["used_by"] == ["L1.tub"] and fact["source"]["hash"] == last["hash"]
    [strike] = recalled["strikes"]
    assert (strike["line_id"], strike["product_key"], strike["by"]) == (product["line_id"], product["product_key"], "issuer")
    assert strike["reason"] == "the suction cup lets go on tile" and strike["at"]
    assert {a["store"] for a in recalled["store_answers"]} == set(sheet["stores"])
    assert all(a["age"]["seconds"] > 0 and a["asked_at"] and a["source"]["file"].startswith("data/store_answers/")
               for a in recalled["store_answers"])
    assert recalled["counts"]["recalled"] == 2 + len(recalled["store_answers"]) <= recalled["counts"]["of"]


def test_a_later_signed_unstrike_ends_the_memory_of_the_strike(records, sheet, product):
    receipts.start("sheet sheet4")
    signed_strike(product, "too flimsy", seq=1)
    assert len(memory.recall(sheet)["strikes"]) == 1
    signed_strike(product, None, kind="unstrike", seq=2)
    assert memory.recall(sheet)["strikes"] == []


def test_a_memory_of_another_persons_sheet_is_not_recalled(records, sheet, product):
    receipts.start("sheet sheet4")
    _measure(22.5)
    signed_strike(product, "too flimsy")
    other = json.loads(json.dumps(sheet))
    other["shopper"]["id"], other["issuer"]["id"] = "someone-else", "another-approver"
    recalled = memory.recall(other)
    assert recalled["facts"] == [] and recalled["strikes"] == []


def test_a_row_put_in_the_store_by_hand_is_never_recalled_and_is_shown_as_not_proved(records, sheet):
    receipts.start("sheet sheet4")
    _measure(22.5)
    memory.sync()
    forged = {"id": "m_forged", "owner": "shopper", "owner_id": "elena", "owner_name": "Elena", "kind": "home_measurement",
              "key": "door_clear_opening", "value": {"value": 35.0, "unit": "in"}, "text": "Elena measured the door: 35 in.",
              "source": {"type": "receipt", "chain": "20260101T000000.000000", "n": 2, "hash": "0" * 64},
              "created_at": "2026-11-20T23:59:00-08:00", "sheet_id": "sheet4"}
    with open(store.mirror_file(), "a") as f:
        f.write(json.dumps(forged) + "\n")
    assert [f["fact_id"] for f in memory.recall(sheet)["facts"]] == ["tub_inside_width"]
    held = memory.read()
    assert held["read_from"].startswith("mirror (database not reached")  # the reply says the mirror was used
    assert [r["id"] for r in held["rows"] if not r["proved"]] == ["m_forged"]


def test_a_run_that_keeps_no_receipts_on_disk_remembers_nothing_from_them(records, sheet, monkeypatch):
    receipts.start("sheet sheet4")
    _measure(22.5)
    assert len(memory.recall(sheet)["facts"]) == 1
    monkeypatch.setenv("SIGNOFF_RECEIPTS", "memory")
    assert memory.recall(sheet)["facts"] == []


def test_recall_never_raises(records, monkeypatch):
    assert memory.recall(None)["error"] is None
    monkeypatch.setattr(store, "sync", lambda **_: 1 / 0)
    recalled = memory.recall({"id": "sheet4"})
    assert recalled["facts"] == [] and recalled["strikes"] == [] and "ZeroDivisionError" in recalled["error"]


def test_the_routes_group_by_owner_and_say_why_a_memory_bears_on_an_item(records, sheet, product, monkeypatch):
    receipts.start("sheet sheet4")
    _measure(22.5)
    signed_strike(product, "too flimsy")
    monkeypatch.setattr(api, "_active_sheet", lambda: sheet)
    app = FastAPI()
    app.include_router(api.router)
    client = TestClient(app)
    everything = client.get("/api/memory").json()
    owners = {o["owner"]: o for o in everything["owners"]}
    assert {"shopper", "issuer", *sheet["stores"]} <= set(owners)
    assert all(r["source"] and r["proved"] for o in everything["owners"] for r in o["rows"])
    assert everything["counts"]["rows"] == everything["counts"]["proved"] and "mirror" in everything["read_from"]
    one = client.get("/api/memory/recall", params={"line_id": product["line_id"]}).json()
    assert [r["kind"] for r in one["recalled"] if r["kind"] != "store_answer"] == ["strike"]
    tub = client.get("/api/memory/recall", params={"line_id": "L1"}).json()
    assert [(r["kind"], r["why"]) for r in tub["recalled"] if r["kind"] == "home_measurement"] == [
        ("home_measurement", 'bounds "fits inside the tub" on this item')]
    assert client.get("/api/memory/recall", params={"line_id": "nope"}).json()["error"]


@pytest.mark.live
def test_rows_reach_singlestore_and_come_back(records, sheet, monkeypatch):
    import uuid
    name = "memory_test_" + uuid.uuid4().hex[:8]
    monkeypatch.setenv("SIGNOFF_MEMORY_TABLE", name)
    monkeypatch.delenv("SIGNOFF_MEMORY_DB")
    receipts.start("sheet sheet4")
    _measure(22.5)
    try:
        held = memory.read()
        assert held["read_from"] == "singlestore" and held["database"]["state"] == "ok"
        assert len(held["rows"]) == len(store.mirror_rows()) and all(r["proved"] for r in held["rows"])
        assert any(r["kind"] == "home_measurement" and r["value"]["value"] == 22.5 for r in held["rows"])
    finally:
        store._in_db(lambda conn: conn.cursor().execute("DROP TABLE IF EXISTS %s" % name))


def test_the_context_count_says_which_model_calls_were_given_memory():
    from signoff.memory import meaning
    rows = [{"kind": "model", "recipient": "anthropic:reader", "purpose": "read figures from one store page", "bytes": 3000,
             "fact_classes": ["product", "store_text"], "sealed_found_in_payload": []}] * 3 + [
            {"kind": "model", "recipient": meaning.RECIPIENT, "purpose": meaning.PURPOSE_INDEX, "bytes": 900,
             "fact_classes": ["home_measurement", "store_text"], "sealed_found_in_payload": ["home_measurement: 22.5 in"]},
            {"kind": "store", "recipient": "carex.com", "purpose": "ask", "bytes": 10, "fact_classes": ["none"]}]
    told = meaning.context(rows)
    assert (told["model_calls"], told["calls_given_memory"], told["calls_given_no_memory"]) == (4, 1, 3)
    reader = told["by_call"][0]
    assert (reader["calls"], reader["calls_given_memory"], reader["given"], reader["payloads_containing_a_home_value"]) == (
        3, 0, ["product", "store_text"], 0)


def test_recall_by_meaning_never_raises_and_says_when_it_did_not_run(records, sheet, monkeypatch):
    from signoff.memory import meaning
    monkeypatch.setattr(meaning, "embed", lambda *a, **k: 1 / 0)
    monkeypatch.setattr(meaning, "_queries", {})
    recalled = memory.recall(sheet)
    told = meaning.search(sheet, "L5", recalled)
    assert told["ranked"] == [] and "ZeroDivisionError" in told["error"] and told["query"].startswith("grab bar")
    assert meaning.search(sheet, "nope", recalled)["error"]


@pytest.mark.live
def test_meaning_ranks_the_memories_about_the_item_first(records, sheet, product, monkeypatch):
    import uuid
    from signoff.memory import meaning
    name = "memory_test_" + uuid.uuid4().hex[:8]
    monkeypatch.setenv("SIGNOFF_MEMORY_TABLE", name)
    monkeypatch.delenv("SIGNOFF_MEMORY_DB")
    monkeypatch.setattr(meaning, "_queries", {})
    receipts.start("sheet sheet4")
    _measure(22.5)
    signed_strike(product, "the suction cup lets go on tile")
    try:
        done = meaning.index(timeout_s=600)
        assert done["indexed"] == done["of"] > 0
        recalled = memory.recall(sheet)
        told = meaning.search(sheet, product["line_id"], recalled, k=3, timeout_s=120)
        assert told["error"] is None and told["recalled"] == 3 and told["of"] == recalled["counts"]["recalled"]
        assert told["not_indexed_yet"] == 0
        assert told["ranked"][0]["kind"] == "strike" and told["ranked"][0]["key"] == product["product_key"]
        assert all(r["owner"] in ("shopper", "issuer", *sheet["stores"]) for r in told["ranked"])
        only_stores = meaning.search(sheet, product["line_id"], recalled, k=3, kinds=["store_answer"], timeout_s=120)
        assert {r["kind"] for r in only_stores["ranked"]} == {"store_answer"}
    finally:
        for table in (name, name + "_vec"):
            store._in_db(lambda conn: conn.cursor().execute("DROP TABLE IF EXISTS %s" % table))
