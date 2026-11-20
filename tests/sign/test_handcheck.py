import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.sign import handcheck


@pytest.fixture
def hc(tmp_path, monkeypatch):
    monkeypatch.setattr(handcheck, "ANSWERS", tmp_path / "handcheck.jsonl")
    monkeypatch.setattr(handcheck, "SAMPLE", tmp_path / "sample.json")
    fixture_pool = json.loads((handcheck.ROOT / "fixtures" / "pool.json").read_text())
    monkeypatch.setattr(handcheck, "load_pool", lambda: (fixture_pool, "fixtures/pool.json (placeholder products)"))
    app = FastAPI()
    app.include_router(handcheck.router)
    return TestClient(app)


def pool(n_per_store=14):
    return [{"store": s, "product_id": "%s-%d" % (s, i), "variant_id": "v", "title": "t", "price_cents": 100,
             "url": "u", "text": "Holds 300 lb.", "product_key": "%s %d" % (s, i), "line_ids": ["L%d" % (i % 6 + 1)]}
            for s in ("a.com", "b.com", "c.com") for i in range(n_per_store)]


def test_sample_is_30_spread_over_stores_and_lines():
    sample = handcheck.pick_sample(pool())
    assert len(sample) == 30 and len({p["product_id"] for p in sample}) == 30
    assert {s: sum(p["store"] == s for p in sample) for s in ("a.com", "b.com", "c.com")} == {"a.com": 10, "b.com": 10, "c.com": 10}
    assert len({p["line_ids"][0] for p in sample}) == 6


def test_sample_tops_up_when_a_store_is_small():
    small = [p for p in pool() if p["store"] != "c.com" or int(p["product_id"].split("-")[1]) < 3]
    assert len(handcheck.pick_sample(small)) == 30


def test_save_roundtrip_and_resume(hc):
    body = {"store": "a.com", "product_id": "p1", "product_key": "k", "title": "T", "weight_capacity": 300,
            "height": None, "overall_width": 22.5, "height_kind": "none"}
    r = hc.post("/api/handcheck/save", json=body)
    assert r.status_code == 200 and r.json()["done"] == 1
    rows = [json.loads(l) for l in handcheck.ANSWERS.read_text().splitlines()]
    assert rows[0]["height"] is None and rows[0]["overall_width"] == 22.5 and rows[0]["weight_capacity"] == 300.0
    hc.post("/api/handcheck/save", json={**body, "weight_capacity": 350})  # editing replaces, never duplicates
    rows = [json.loads(l) for l in handcheck.ANSWERS.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["weight_capacity"] == 350.0


def test_unfinished_or_odd_rows_are_refused(hc):
    base = {"store": "a.com", "product_id": "p1", "weight_capacity": 300, "height": 5, "overall_width": None, "height_kind": "added_height"}
    assert hc.post("/api/handcheck/save", json={k: v for k, v in base.items() if k != "overall_width"}).status_code == 400
    assert hc.post("/api/handcheck/save", json={**base, "height_kind": "none"}).status_code == 400
    assert hc.post("/api/handcheck/save", json={**base, "weight_capacity": "300"}).status_code == 400
    assert not handcheck.ANSWERS.exists()


def test_page_and_items_are_served(hc):
    assert "Hand-check sheet" in hc.get("/handcheck/").text
    body = hc.get("/api/handcheck/items").json()
    assert body["total"] == 19 and "placeholder" in body["source"]
    assert not handcheck.SAMPLE.exists()  # placeholder products are never pinned
