"""Real carts, one per store. Called only by the SIGN stream after a verified signature.

Only create_cart is called here. No checkout tool exists in signoff.store.ucp (ALLOWED_TOOLS), by design.
"""
import datetime
from collections import defaultdict

from signoff import config
from signoff.store import ucp


def _cart_url(cart: dict) -> str | None:
    c = cart.get("cart", cart)
    return c.get("continue_url")


def create_carts(picks: list[dict]) -> list[dict]:
    """picks: [{store, variant_id, quantity}] -> [{store, cart_id, cart_url, total_cents, created_at, mode}], one per store."""
    by_store: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        by_store[p["store"]].append(p)
    out = []
    for store, items in by_store.items():
        r = ucp.call(store, "create_cart", {"cart": {"line_items": [
            {"item": {"id": i["variant_id"]}, "quantity": int(i.get("quantity", 1))} for i in items]}})
        c = r.get("cart", r)
        url = _cart_url(r)
        if not url:
            raise RuntimeError(f"{store} returned no continue_url")
        totals = c.get("totals") or []
        total = next((t.get("amount") for t in totals if t.get("type") in ("total", "grand_total")), None)
        if total is None and totals:
            total = totals[-1].get("amount")
        out.append({"store": store, "cart_id": c.get("id"), "cart_url": url, "total_cents": total,
                    "created_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                    "mode": "replay" if r.get("mode") == "replay" else config.mode()})
    return out
