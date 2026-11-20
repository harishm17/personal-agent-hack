import json
import pathlib

from signoff.store import ask, cart, replay, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used in replay mode")
    monkeypatch.setattr(ucp.urllib.request, "urlopen", boom)
    monkeypatch.setenv("SIGNOFF_MODE", "replay")


def test_replay_search_ask_cart_without_network(monkeypatch):
    _no_network(monkeypatch)
    r = ucp.search_catalog("carex.com", "raised toilet seat")
    assert r["mode"] == "replay" and len(r["products"]) >= 5
    a = ask.ask("carex.com")
    assert a["mode"] == "replay" and "cannot be returned" in a["answer"]
    pool = json.loads((ROOT / "data" / "pool" / "carex.com.json").read_text())
    out = cart.create_carts([{"store": "carex.com", "variant_id": pool[0]["variant_id"], "quantity": 2},
                             {"store": "carex.com", "variant_id": pool[1]["variant_id"], "quantity": 1}])
    assert len(out) == 1 and out[0]["mode"] == "replay"
    assert out[0]["total_cents"] == pool[0]["price_cents"] * 2 + pool[1]["price_cents"]
    assert out[0]["cart_url"] == pool[0]["url"]


def test_replay_unknown_query_is_empty_not_an_error(monkeypatch):
    _no_network(monkeypatch)
    assert ucp.search_catalog("carex.com", "no such thing")["products"] == []


def test_replay_serves_sheet2_search_ask_and_cart_without_network(monkeypatch):
    _no_network(monkeypatch)
    sheet = json.loads((ROOT / "sheets" / "sheet2.json").read_text())
    for store in sheet["stores"]:
        r = ucp.search_catalog(store, "toilet" if store != "kingstonbrass.com" else "shower head")
        assert r["mode"] == "replay" and r["products"], store
        a = ask.ask(store)
        assert a["mode"] == "replay" and a["answer"] and "toilet" in a["question"]
    pool = json.loads((ROOT / "data" / "sheet2" / "pool" / "horow.com.json").read_text())
    opt = next(p for p in pool if len(p["options"]) >= 1)["options"][0]
    out = cart.create_carts([{"store": "horow.com", "variant_id": opt["variant_id"], "quantity": 1}])
    assert out[0]["mode"] == "replay" and out[0]["total_cents"] is not None and out[0]["cart_url"].startswith("https://")


def test_replay_serves_sheet3_search_ask_and_cart_without_network(monkeypatch):
    _no_network(monkeypatch)
    sheet = json.loads((ROOT / "sheets" / "sheet3.json").read_text())
    first_query = {line["id"]: line["queries"][0] for line in sheet["lines"]}
    for store in ("jlab.com", "bazicproducts.com", "pencils.com", "yoobi.com"):
        for q in set(first_query.values()):
            assert ucp.search_catalog(store, q)["mode"] == "replay"
        a = ask.ask(store)
        assert a["mode"] == "replay" and a["answer"]
    assert ucp.search_catalog("bazicproducts.com", "crayons")["products"]
    pool = json.loads((ROOT / "data" / "sheet3" / "pool" / "bazicproducts.com.json").read_text())
    opt = pool[0]["options"][0]
    out = cart.create_carts([{"store": "bazicproducts.com", "variant_id": opt["variant_id"], "quantity": 2}])[0]
    assert out["mode"] == "replay" and out["total_cents"] == 2 * opt["price_cents"] and out["lines"][0]["quantity"] == 2


def test_a_sheet_with_data_from_uses_the_pool_and_answers_of_the_sheet_it_names(monkeypatch):
    from signoff.store import pool as pool_mod, sheetctx
    assert sheetctx.data_id("sheet4") == "sheet1" and sheetctx.data_id("sheet3") == "sheet3"
    assert sheetctx.pool_dir("sheet4") == sheetctx.pool_dir("sheet1") and sheetctx.answers_dir("sheet4") == sheetctx.answers_dir("sheet1")
    pool, answers = pool_mod.load("sheet4")
    assert {p["store"] for p in pool} == {"carex.com", "vivehealth.com", "parentgiving.com"} and answers
    _no_network(monkeypatch)
    monkeypatch.setattr(sheetctx, "active_id", lambda: "sheet4")
    r = ucp.search_catalog("carex.com", "walker")
    assert r["mode"] == "replay" and r["products"]
    opt = next(p for p in pool if p["store"] == "carex.com")["options"][0]
    assert cart.create_carts([{"store": "carex.com", "variant_id": opt["variant_id"], "quantity": 1}])[0]["mode"] == "replay"
