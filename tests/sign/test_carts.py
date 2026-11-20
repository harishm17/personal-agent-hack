"""signoff.sign.carts keeps the store's lines; the comparison with the signed picks uses them."""
from signoff.sign import api, carts

REPLY = {"cart": {"id": "gid://c/1", "currency": "USD", "continue_url": "https://s/cart/c/1",
                  "totals": [{"type": "subtotal", "amount": 3110}, {"type": "total", "amount": 3110}],
                  "line_items": [{"id": "gid://line/1", "item": {"id": "gid://v/1", "title": "Seat", "price": 3110}, "quantity": 1}]}}


def test_the_lines_and_currency_of_the_stores_reply_are_kept(monkeypatch):
    monkeypatch.setattr(carts.ucp, "call", lambda store, tool, args, retries=2, timeout=None: REPLY)
    out = carts.create_carts([{"store": "carex.com", "variant_id": "gid://v/1", "quantity": 1}])
    assert out[0]["lines"] == [{"variant_id": "gid://v/1", "quantity": 1, "unit_price_cents": 3110, "title": "Seat"}]
    assert out[0]["currency"] == "USD" and out[0]["total_cents"] == 3110 and out[0]["cart_url"] == "https://s/cart/c/1"


def test_a_reply_without_lines_says_so_and_is_reported_as_not_compared(monkeypatch):
    replay = {"id": "replay-1", "currency": "USD", "mode": "replay", "continue_url": "https://s/p", "totals": [{"type": "total", "amount": 100}]}
    monkeypatch.setattr(carts.ucp, "call", lambda *a, **k: replay)
    out = carts.create_carts([{"store": "carex.com", "variant_id": "gid://v/1", "quantity": 1}])
    assert out[0]["lines"] is None and out[0]["mode"] == "replay"
    picks = [{"store": "carex.com", "variant_id": "gid://v/1", "quantity": 1, "price_cents": 100}]
    assert api._check_lines(out, picks)[0]["lines_checked"] is False


def test_the_real_reply_shape_is_compared_with_the_signed_picks(monkeypatch):
    monkeypatch.setattr(carts.ucp, "call", lambda *a, **k: REPLY)
    out = carts.create_carts([{"store": "carex.com", "variant_id": "gid://v/1", "quantity": 1}])
    same = [{"store": "carex.com", "variant_id": "gid://v/1", "quantity": 1, "price_cents": 3110}]
    assert api._check_lines(out, same)[0]["lines_checked"] is True and "line_differences" not in api._check_lines(out, same)[0]
    moved = [{"store": "carex.com", "variant_id": "gid://v/1", "quantity": 1, "price_cents": 2999}]   # the price moved since the pool
    c = api._check_lines(out, moved)[0]
    assert c["line_differences"] == [{"variant_id": "gid://v/1", "field": "unit price", "signed": 2999, "store": 3110}]
    assert "unit price: signed 2999, store 3110" in c["note"]


def test_a_store_that_errors_is_failed_and_a_timeout_is_pending(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("HTTP 500 from the store")
    monkeypatch.setattr(carts.ucp, "call", boom)
    err = api._label_failure(carts.create_carts([{"store": "a.com", "variant_id": "v", "quantity": 1}])[0])
    assert err["mode"] == "failed" and "HTTP 500" in err["note"]
    slow = api._label_failure({"store": "a.com", "cart_url": None, "mode": "pending", "error": "TimeoutError: timed out"})
    assert slow["mode"] == "pending"
