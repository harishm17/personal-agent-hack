from signoff.store import cart, ucp


def test_create_carts_one_per_store_and_never_checkout(monkeypatch):
    calls = []

    def fake(store, tool, args, **kw):
        calls.append((store, tool))
        return {"id": "gid://cart/" + store, "totals": [{"type": "subtotal", "amount": 5}, {"type": "total", "amount": 7}],
                "continue_url": "https://" + store + "/cart/c/x"}

    monkeypatch.setattr(ucp, "call", fake)
    out = cart.create_carts([{"store": "a.com", "variant_id": "v1", "quantity": 1},
                             {"store": "a.com", "variant_id": "v2", "quantity": 2},
                             {"store": "b.com", "variant_id": "v3", "quantity": 1}])
    assert [o["store"] for o in out] == ["a.com", "b.com"]
    assert out[0]["cart_url"].startswith("https://a.com") and out[0]["total_cents"] == 7
    assert {t for _, t in calls} == {"create_cart"}


def test_checkout_tools_are_refused():
    for tool in ("complete_checkout", "create_checkout", "update_checkout"):
        try:
            ucp.call("carex.com", tool, {})
        except RuntimeError as e:
            assert "not allowed" in str(e)
        else:
            raise AssertionError(tool)


def test_a_store_that_does_not_answer_is_pending_not_an_exception(monkeypatch):
    seen = {}

    def fake(store, tool, args, retries=2, timeout=60):
        seen[store] = (retries, timeout)
        if store == "slow.com":
            raise RuntimeError("timed out")
        return {"id": "c", "totals": [{"type": "total", "amount": 9}], "continue_url": "https://" + store + "/c"}

    monkeypatch.setattr(ucp, "call", fake)
    out = cart.create_carts([{"store": "ok.com", "variant_id": "v", "quantity": 1},
                             {"store": "slow.com", "variant_id": "w", "quantity": 1}], timeout_s=3, tries=1)
    assert [o["store"] for o in out] == ["ok.com", "slow.com"]
    assert out[0]["mode"] == "live" or out[0]["mode"] == cart.config.mode()
    assert out[1]["mode"] == "pending" and out[1]["cart_url"] is None and "timed out" in out[1]["error"]
    assert seen == {"ok.com": (0, 3), "slow.com": (0, 3)}


def test_a_cart_carries_its_lines_and_currency(monkeypatch):
    def fake(store, tool, args, **kw):
        return {"id": "c", "currency": "USD", "totals": [{"type": "total", "amount": 30}], "continue_url": "https://x/c",
                "line_items": [{"id": "l", "quantity": 2, "item": {"id": "v1", "title": "Thing", "price": 15}}]}
    monkeypatch.setattr(ucp, "call", fake)
    out = cart.create_carts([{"store": "a.com", "variant_id": "v1", "quantity": 2}])[0]
    assert out["currency"] == "USD" and out["lines"] == [{"variant_id": "v1", "quantity": 2, "unit_price_cents": 15, "title": "Thing"}]


def test_a_replayed_cart_returns_its_lines_in_the_same_shape(monkeypatch):
    import json
    monkeypatch.setenv("SIGNOFF_MODE", "replay")
    pool = json.loads((cart.__file__ and __import__("pathlib").Path(cart.__file__).resolve().parents[2] / "data" / "sheet2" / "pool" / "swissmadison.com.json").read_text())
    o = pool[0]["options"][0]
    out = cart.create_carts([{"store": "swissmadison.com", "variant_id": o["variant_id"], "quantity": 3}])[0]
    assert out["mode"] == "replay" and out["lines"][0]["variant_id"] == o["variant_id"] and out["lines"][0]["quantity"] == 3
    assert out["lines"][0]["unit_price_cents"] == o["price_cents"] and out["total_cents"] == 3 * o["price_cents"]
