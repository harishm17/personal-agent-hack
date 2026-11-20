"""The graph is built from records only: every node and edge has an owner and a source, and nothing else gets in."""
import copy
import json
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.graph import api, build, cognee, sync

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
STATES = ["fixtures/state.json", "web/screen/fixture-signed.json", "web/screen/fixture-sheet3.json"]


def load(name):
    return json.loads((ROOT / name).read_text())


def receipt(n, kind, **detail):
    return {"n": n, "at": "2026-11-20T12:00:0%d-08:00" % n, "type": kind, "actor": "issuer", "hash": "%064x" % n, "detail": detail}


@pytest.mark.parametrize("name", STATES)
def test_every_node_and_edge_has_an_owner_and_a_source(name):
    g = build.build(load(name))
    assert g["nodes"] and g["edges"]
    ids = {n["id"] for n in g["nodes"]}
    for n in g["nodes"]:
        assert n["kind"] in build.KINDS and n["owner"] and n["source"].get("record"), n
        assert n["label"], n
    for e in g["edges"]:
        assert e["verb"] in build.VERBS and e["owner"] and e["source"].get("record"), e
        assert e["from"] in ids and e["to"] in ids, e


def test_a_strike_or_signature_without_its_receipt_is_left_out_and_counted():
    state = load("web/screen/fixture-signed.json")
    g = build.build(state, receipts=[])
    kinds = {n["kind"] for n in g["nodes"]}
    assert "strike" not in kinds and "purchase" not in kinds
    assert {s["kind"] for s in g["skipped"]} == {"strike", "purchase"}


def test_a_strike_and_a_signature_take_their_receipts_as_source():
    state = load("web/screen/fixture-signed.json")
    struck = next(s for line in state["lines"] for s in line["struck"])
    chain = [receipt(1, "strike", line_id=struck["line_id"], product_key=struck["product_key"]),
             receipt(2, "signed", sheet_hash=state["seal"]["sheet_hash"])]
    g = build.build(state, receipts=chain)
    strike = next(n for n in g["nodes"] if n["kind"] == "strike")
    purchase = next(n for n in g["nodes"] if n["kind"] == "purchase")
    assert strike["source"] == {"record": "receipt", "hash": chain[0]["hash"], "n": 1, "type": "strike", "at": chain[0]["at"]}
    assert strike["text"] == struck["reason"] and strike["owner"] == "issuer"
    assert purchase["source"]["hash"] == chain[1]["hash"]
    verbs = {(e["verb"], e["to"]) for e in g["edges"] if e["from"] == "person:issuer"}
    assert ("struck", strike["id"]) in verbs and ("signed", purchase["id"]) in verbs
    assert not g["skipped"]


def test_a_changed_measurement_is_sourced_to_the_shoppers_receipt():
    state = load("fixtures/state.json")
    fact = state["sheet"]["shopper_facts"][0]
    g = build.build(state, receipts=[receipt(3, "shopper_fact", fact_id=fact["id"])])
    node = next(n for n in g["nodes"] if n["id"] == "fact:" + fact["id"])
    assert node["source"]["record"] == "receipt" and node["owner"] == "shopper"
    other = next(n for n in g["nodes"] if n["kind"] == "home_fact" and n["id"] != node["id"])
    assert other["source"]["record"] == "sheet"


def test_a_limit_points_at_the_orders_own_sentence():
    state = load("fixtures/state.json")
    state = copy.deepcopy(state)
    order = "Order.\n1. Chair. It must hold at least 300 lb.\n2. Other."
    limit = state["sheet"]["lines"][0]["limits"][0]
    start = order.index("It must")
    limit["from_order"] = {"doc": "sheets/x_order.txt", "quote": "It must hold at least 300 lb.", "start": start,
                           "end": start + 29, "span_found_in_text": True}
    state["sheet"]["order_doc"] = "sheets/x_order.txt"
    g = build.build(state, order_text=order)
    node = next(n for n in g["nodes"] if n["id"] == "limit:" + limit["id"])
    assert node["source"] == {"record": "order", "file": "sheets/x_order.txt", "start": start, "end": start + 29}
    assert order[node["source"]["start"]:node["source"]["end"]] == node["text"]
    item = next(n for n in g["nodes"] if n["id"] == "item:" + state["sheet"]["lines"][0]["id"])
    assert order[item["source"]["start"]:item["source"]["end"]] == "1. Chair. It must hold at least 300 lb."


def test_memory_gives_a_source_only_when_a_record_proves_it():
    state = load("web/screen/fixture-signed.json")
    struck = next(s for line in state["lines"] for s in line["struck"])
    fact = state["sheet"]["shopper_facts"][0]
    earlier = {"type": "receipt", "chain": "c0", "n": 4, "hash": "ab" * 32, "at": "2026-11-20T10:00:00-08:00"}
    rows = [{"id": "m1", "owner": "issuer", "kind": "strike", "key": struck["product_key"], "proved": True,
             "value": {"struck": True, "line_id": struck["line_id"]}, "source": earlier, "created_at": "1"},
            {"id": "m2", "owner": "shopper", "kind": "home_measurement", "key": fact["id"], "proved": False,
             "value": {}, "source": earlier, "created_at": "1"},
            {"id": "m3", "owner": "shopper", "kind": "home_measurement", "key": fact["id"], "proved": True,
             "value": {}, "source": None, "created_at": "1"}]
    g = build.build(state, receipts=[], memory=rows)
    strike = next(n for n in g["nodes"] if n["kind"] == "strike")
    assert strike["remembered"] is True and strike["label"] == "struck before"
    assert strike["source"] == dict(earlier, record="memory", memory_id="m1")
    # a row no record proves, and a row with no source, change nothing
    node = next(n for n in g["nodes"] if n["id"] == "fact:" + fact["id"])
    assert node["source"]["record"] == "sheet" and "remembered" not in node
    assert {s["id"] for s in g["skipped"]} >= {"memory:m2", "memory:m3"}
    assert g["memory"] == {"proved_rows": 1, "used_as_source": 1}


@pytest.mark.parametrize("name", STATES)
def test_an_items_view_is_small_complete_and_folds_the_rest(name):
    state = load(name)
    g = build.build(state)
    for line in state["lines"]:
        v = build.view(g, line["line_id"])
        nodes = {n["id"]: n for n in v["nodes"]}
        products = [n for n in v["nodes"] if n["kind"] == "product"]
        every = [n for n in g["nodes"] if n["kind"] == "product" and n["line_id"] == line["line_id"]]
        assert len(v["nodes"]) <= 30
        assert "item:" + line["line_id"] in nodes
        assert {n["id"] for n in every if n.get("picked")} <= set(nodes)
        assert len(products) + v["folded"]["products"] == len(every)
        assert sum(v["folded"]["by_status"].values()) == v["folded"]["products"]
        assert all(n["line_id"] == line["line_id"] for n in v["nodes"] if n.get("line_id"))
        tied = {x for e in v["edges"] for x in (e["from"], e["to"])}
        assert tied <= set(nodes)
        assert all(n["id"] in tied for n in v["nodes"] if n["kind"] in ("person", "store", "statement"))
    assert build.view(g, "no-such-line") is None


def test_each_owners_sentences_stay_in_that_owners_dataset():
    state = load("fixtures/state.json")
    g = build.build(state)
    texts = sync.sentences(build.view(g, state["lines"][0]["line_id"]), {"issuer": "Dana", "shopper": "Elena"})
    stores = {n["owner"] for n in g["nodes"] if n["kind"] == "store"}
    assert stores >= {c["product"]["store"] for line in state["lines"] for c in line["candidates"]}
    assert set(texts) <= {"issuer", "shopper", "system"} | stores
    assert all("Source:" in s for owner in texts for s in texts[owner])
    assert all("measured" not in s for s in texts["issuer"])
    assert all(s.startswith("Elena measured") for s in texts.get("shopper", []))


def client(monkeypatch, state):
    monkeypatch.setattr(api.records, "read", lambda: {"state": state, "receipts": [], "order_text": None, "memory": [],
                                                      "memory_available": False, "read_from": "a test"})
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def test_the_route_names_its_backend(monkeypatch, tmp_path):
    monkeypatch.setattr(cognee, "FACTS", tmp_path / "cognee.json")
    monkeypatch.setattr(cognee, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(api, "ANSWERS", tmp_path / "answers")
    state = load("fixtures/state.json")
    c = client(monkeypatch, state)
    line = state["lines"][0]["line_id"]
    body = c.get("/api/graph", params={"line_id": line}).json()
    assert body["backend"] == "records" and body["nodes"] and body["edges"] and body["line_id"] == line
    assert body["cognee"]["holds"] is False
    whole = c.get("/api/graph").json()
    assert whole["backend"] == "records" and "nodes" not in whole and whole["whole"]["nodes"] > len(body["nodes"])
    assert c.get("/api/graph", params={"line_id": "nope"}).status_code == 404
    # no answer is made up when Cognee has not been asked
    asked = c.get("/api/graph/ask", params={"line_id": line}).json()
    assert asked == {"backend": "cognee", "answered": False, "line_id": line, "note": "Cognee has not been asked about this item"}


def test_when_cognee_cannot_answer_the_reply_says_so_and_it_is_logged(monkeypatch, tmp_path):
    monkeypatch.setattr(cognee, "FACTS", tmp_path / "cognee.json")
    monkeypatch.setattr(cognee, "LOG", tmp_path / "log.jsonl")
    monkeypatch.setattr(api, "ANSWERS", tmp_path / "answers")

    def down(*args, **kwargs):
        raise cognee.CogneeError("search 503: down")
    monkeypatch.setattr(cognee, "ask", down)
    state = load("fixtures/state.json")
    line = state["lines"][0]["line_id"]
    r = client(monkeypatch, state).post("/api/graph/ask", params={"line_id": line})
    assert r.status_code == 502
    assert r.json()["backend"] == "cognee" and r.json()["answered"] is False and "answer" not in r.json()
    assert cognee.read_log()[-1]["status"] == 502
    assert not (tmp_path / "answers").exists()


@pytest.mark.live
def test_cognee_refuses_the_shoppers_key_on_the_issuers_dataset():
    before = len(cognee.read_log())
    cognee.setup(["issuer", "shopper"])
    refused = cognee.write("shopper", "issuer", ["Our order requires nothing at all."], "a live test of the refusal")
    assert refused["accepted"] is False and "permission" in refused["reply"].lower()
    assert len(cognee.read_log()) == before + 1
