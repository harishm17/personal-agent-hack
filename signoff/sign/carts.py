"""Carts for the signed picks, one per store, with the lines the store reports.

Same calls as `signoff.store.cart.create_carts` (create_cart only, through `signoff.store.ucp`), but each result also
carries `lines` (variant id, quantity, unit price in cents, title) and `currency` from the store's own reply, so SIGN
can compare what the store put in the cart with what was signed. In replay mode no cart exists and the reply has no
lines; the result says so (`lines` is None) and the comparison is reported as not made. If STORE's create_carts later
returns `lines` itself, `signoff/sign/api.py::get_cart` can point back at it."""
from __future__ import annotations

import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from signoff import config
from signoff.store import ucp


def _now() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def lines_of(cart: dict) -> list[dict] | None:
    """`cart.line_items[]` is `{item: {id, title, price}, quantity}`; None when the reply has none (replay)."""
    items = cart.get("line_items")
    if not isinstance(items, list):
        return None
    return [{"variant_id": (l.get("item") or {}).get("id"), "quantity": l.get("quantity", 1),
             "unit_price_cents": (l.get("item") or {}).get("price"), "title": (l.get("item") or {}).get("title")} for l in items]


def _one(store: str, items: list[dict], timeout_s: float, tries: int) -> dict:
    try:
        r = ucp.call(store, "create_cart", {"cart": {"line_items": [
            {"item": {"id": i["variant_id"]}, "quantity": int(i.get("quantity", 1))} for i in items]}},
            retries=max(0, tries - 1), timeout=timeout_s)
        c = r.get("cart", r)
        url = c.get("continue_url")
        if not url:
            raise RuntimeError("no continue_url in the store's reply")
        totals = c.get("totals") or []
        total = next((t.get("amount") for t in totals if t.get("type") in ("total", "grand_total")), None)
        if total is None and totals:
            total = totals[-1].get("amount")
        return {"store": store, "cart_id": c.get("id"), "cart_url": url, "total_cents": total, "created_at": _now(),
                "mode": "replay" if r.get("mode") == "replay" else config.mode(), "currency": c.get("currency"),
                "lines": lines_of(c)}
    except Exception as e:  # noqa: BLE001
        return {"store": store, "cart_id": None, "cart_url": None, "total_cents": None, "created_at": _now(),
                "mode": "pending", "error": (type(e).__name__ + ": " + str(e))[:240]}


def create_carts(picks: list[dict], timeout_s: float = 30.0, tries: int = 2) -> list[dict]:
    by_store: dict[str, list[dict]] = defaultdict(list)
    for p in picks:
        by_store[p["store"]].append(p)
    with ThreadPoolExecutor(max_workers=max(1, len(by_store))) as ex:
        futures = [ex.submit(_one, store, items, timeout_s, tries) for store, items in by_store.items()]
        return [f.result() for f in futures]
