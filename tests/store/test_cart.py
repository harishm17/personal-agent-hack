from signoff.store import cart, ucp


def test_create_carts_one_per_store_and_never_checkout(monkeypatch):
    calls = []

    def fake(store, tool, args):
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
