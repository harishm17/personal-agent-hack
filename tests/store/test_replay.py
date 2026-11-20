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
