"""A small stand-in for signoff.engine.state and signoff.store.cart, built on fixtures/state.json.
Follows the signatures in CONTRACT.md only; the real modules replace it at the first sync."""
import copy
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


class FakeEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = json.loads((ROOT / "fixtures" / "state.json").read_text())
        self.held = False
        self.calls = []
        self.issuer_key = None
        return {"version": 1}

    def get_state(self):
        return copy.deepcopy(self.state)

    def canonical_sheet(self):
        picks = [(l["line_id"], l["pick"]) for l in self.state["lines"]]
        limits = [(l["id"], l["bound"].get("value")) for line in self.state["sheet"]["lines"] for l in line["limits"]]
        return json.dumps({"sheet": self.state["sheet"]["id"], "picks": picks, "limits": limits,
                           "total": self.state["total_cents"]}, sort_keys=True, separators=(",", ":"))

    def sheet_hash(self):
        return hashlib.sha256(self.canonical_sheet().encode()).hexdigest()

    def apply_issuer(self, action):
        self.calls.append(("apply_issuer", action))
        if action["type"] == "set_limit":
            for line in self.state["sheet"]["lines"]:
                for limit in line["limits"]:
                    if limit["id"] == action["limit_id"]:
                        limit["bound"]["value"] = action["value"]
        self.state["version"] += 1
        return {"version": self.state["version"]}

    def signed_picks(self, sheet_hash):
        """Like the engine's: the picks of exactly that hash, refused if it is not the current one; holds the sheet."""
        if sheet_hash != self.sheet_hash():
            err = ValueError("the sheet changed since this hash was made")
            err.status = 409
            raise err
        self.held = True
        picks = []
        for line in self.state["lines"]:
            if line["status"] in ("ready", "next_candidate"):
                c = next(c for c in line["candidates"] if c["picked"])
                picks.append({"store": c["product"]["store"], "variant_id": c["product"]["variant_id"], "quantity": 1,
                              "line_id": line["line_id"], "candidate_id": c["id"], "product_id": c["product"]["product_id"],
                              "title": c["product"]["title"], "price_cents": c["product"]["price_cents"]})
        return picks

    def release_signing(self):
        self.held = False
        self.calls.append(("release_signing",))
        return {"version": self.state["version"]}

    def mark_signed(self, signature, carts):
        if signature.get("sheet_hash") != self.sheet_hash():
            err = ValueError("the sheet changed after it was signed")
            err.status = 409
            raise err
        self.held = False
        self.calls.append(("mark_signed", signature, carts))
        self.state["seal"] = {"signed": True, "text": "Signed", "sheet_hash": signature["sheet_hash"],
                              "signature": signature, "carts": carts}
        self.state["version"] += 1
        return {"version": self.state["version"]}

    def set_issuer_key(self, info):
        self.issuer_key = info


class FakeCart:
    def __init__(self):
        self.calls = []
        self.fail = False

    def create_carts(self, picks):
        self.calls.append(picks)
        if self.fail:
            raise RuntimeError("store down")
        return [{"store": p["store"], "cart_id": "c-" + p["variant_id"], "cart_url": "https://%s/cart/%s" % (p["store"], p["variant_id"]),
                 "total_cents": 100, "created_at": "2026-11-20T12:00:00-08:00", "mode": "live"} for p in picks]
