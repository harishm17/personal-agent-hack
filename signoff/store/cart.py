"""Real carts, one per store. Called only by the SIGN stream after a verified signature.

Only create_cart is called here. No checkout tool exists in signoff.store.ucp (ALLOWED_TOOLS), by design.
"""
import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from signoff import config
from signoff.store import ucp


def _cart_url(cart: dict) -> str | None:
    c = cart.get("cart", cart)
    return c.get("continue_url")


def _one(store: str, items: list[dict], timeout_s: float, tries: int) -> dict:
    now = lambda: datetime.datetime.now().astimezone().isoformat(timespec="seconds")  # noqa: E731
    try:
        r = ucp.call(store, "create_cart", {"cart": {"line_items": [
            {"item": {"id": i["variant_id"]}, "quantity": int(i.get("quantity", 1))} for i in items]}},
            retries=max(0, tries - 1), timeout=timeout_s)
        c = r.get("cart", r)
        url = _cart_url(r)
        if not url:
            raise RuntimeError("no continue_url in the store's reply")
        totals = c.get("totals") or []
        total = next((t.get("amount") for t in totals if t.get("type") in ("total", "grand_total")), None)
        if total is None and totals:
            total = totals[-1].get("amount")
        return {"store": store, "cart_id": c.get("id"), "cart_url": url, "total_cents": total, "created_at": now(),
                "mode": "replay" if r.get("mode") == "replay" else config.mode()}
    except Exception as e:  # noqa: BLE001
        return {"store": store, "cart_id": None, "cart_url": None, "total_cents": None, "created_at": now(),
                "mode": "pending", "error": (type(e).__name__ + ": " + str(e))[:240]}


def create_carts(picks: list[dict], timeout_s: float = 30.0, tries: int = 2) -> list[dict]:
    """picks: [{store, variant_id, quantity}] -> one entry per store, in order of first appearance:
    {store, cart_id, cart_url, total_cents, created_at, mode} with mode "live" or "replay". A store that does not answer in
    `timeout_s` seconds (after `tries` tries) gives {..., mode: "pending", error} and no exception: the caller shows it as
    not yet created. Stores are called at the same time, so the whole call takes about timeout_s x tries at most."""
    by_store: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        by_store[p["store"]].append(p)
    with ThreadPoolExecutor(max_workers=max(1, len(by_store))) as ex:
        futures = [ex.submit(_one, store, items, timeout_s, tries) for store, items in by_store.items()]
        return [f.result() for f in futures]
