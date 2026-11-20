import glob
import json
import pathlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from signoff.airbyte import api, export, pool, sync

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_export_rows_match_the_cached_pool_and_answers():
    on_disk = sum(len(json.load(open(f))) for f in glob.glob(str(ROOT / "data" / "pool" / "*.json")))
    rows = export.pool_rows()
    assert len(rows) == on_disk
    assert all(r["text"] and r["store"] and r["price_cents"] is not None for r in rows)
    answers = export.answer_rows()
    assert {a["store"] for a in answers} == {"carex.com", "vivehealth.com", "parentgiving.com"}


def test_export_order_has_one_row_per_limit_and_says_invented():
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    rows = export.order_rows(sheet)
    assert len(rows) == sum(len(line["limits"]) for line in sheet["lines"])
    assert all("invented" in r["order_note"] for r in rows)


def test_line_ids_become_a_json_array_on_the_way_in():
    cols = sync.COLUMNS["airbyte_pool"]
    row = ["s", "p", "v", "t", 1, "u", "x", "now", "k", "L1,L4"]
    assert len(row) == len(cols)
    assert json.loads(sync._clean("airbyte_pool", row)[-1]) == ["L1", "L4"]


def test_load_returns_none_when_the_database_is_down(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(pool.conn, "connect", boom)
    assert pool.load() is None


def test_status_route_reports_the_last_run(monkeypatch):
    monkeypatch.setattr(api, "_last_run", lambda: {
        "finished_at": "t", "ok": True, "seconds": 70.0, "expected": {"pool": 111},
        "loaded": {"airbyte_pool": 111, "airbyte_store_answers": 3},
        "jobs": [{"stream": "airbyte_pool", "job_id": 5, "connection_id": "c", "status": "succeeded",
                  "rows_synced": 111, "duration": "PT1M"}]})
    app = FastAPI()
    app.include_router(api.router)
    body = TestClient(app).get("/api/airbyte/status").json()
    assert body["source"] == "File (HTTPS)" and body["destination"] == "MySQL (local staging)"
    assert body["copy"] == "copied to SingleStore by signoff.airbyte.sync"
    job = body["last"]["jobs"][0]
    assert (job["job_id"], job["rows_synced"], job["rows_copied_to_singlestore"], job["duration"]) == (5, 111, 111, "PT1M")
    assert "copied to SingleStore by signoff.airbyte.sync" in body["last"]["lines"][0]


@pytest.mark.live
def test_synced_rows_are_in_singlestore_and_equal_the_pool():
    data = pool.load()
    assert data and data["via"] == "airbyte"
    on_disk = {(p["store"], p["product_id"]): p for f in glob.glob(str(ROOT / "data" / "pool" / "*.json"))
               for p in json.load(open(f))}
    got = {(p["store"], p["product_id"]): p for p in data["pool"]}
    assert set(got) == set(on_disk)
    assert all(got[k]["text"] == on_disk[k]["text"] and got[k]["price_cents"] == on_disk[k]["price_cents"] for k in got)


@pytest.mark.live
def test_order_limits_synced_match_the_sheet():
    from signoff.airbyte import order
    data = order.load()
    sheet = json.loads((ROOT / "sheets" / "sheet1.json").read_text())
    want = {lim["id"]: lim for line in sheet["lines"] for lim in line["limits"]}
    assert data and data["rows"] == len(want)
    for r in data["limits"]:
        b = want[r["limit_id"]]["bound"]
        assert r["op"] == want[r["limit_id"]]["op"]
        assert (r["value"] == b["value"]) if b["source"] == "issuer" else r["value"] is None
