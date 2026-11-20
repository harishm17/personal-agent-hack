"""A private sheet for a drill session: the same pool, figures and rules as the live sheet, its own limits
and strikes, and no seal. Nothing done to a sandbox reaches the app's live state, a store or the database.

It offers the same two reads the chat uses (`get_state`, `sheet_hash`). Its only write is `strike`, which a
drill uses once to set up the product the attempts will push on; no route lets a chat message reach it.
"""
import copy
import datetime
import hashlib

from signoff.engine import rules, state


class Sandbox:
    def __init__(self):
        live = state.get_state()  # makes sure the engine has loaded
        self.sheet = copy.deepcopy(state._read(state.SHEETS / (live["sheet"]["id"] + ".json")))
        self.strikes, self._state = [], None
        self.pool, self.figures, self.answers = state._s["pool"], state._s["figures"], state._s["answers"]
        self.start = None

    def get_state(self) -> dict:
        if self._state is None:
            built = rules.build_state(self.sheet, self.pool, self.figures, self.answers, self.strikes, "sandbox")
            built["sheet_hash"] = hashlib.sha256(state._canonical(built).encode()).hexdigest()
            self._state = built
        return self._state

    def sheet_hash(self) -> str:
        return self.get_state()["sheet_hash"]

    def strike(self, line_id, product_key=None, reason="He cannot use a frame with fixed arms"):
        """Strikes a product (the line's current pick when no key is given) and marks the starting point."""
        line = next((l for l in self.get_state()["lines"] if l["line_id"] == line_id), None)
        if line is None:
            raise state.EngineError("no line %r on this sheet" % (line_id,), 404)
        if product_key is None:
            pick = next((c for c in line["candidates"] if c["picked"]), None)
            if pick is None:
                raise state.EngineError("line %s has no pick to strike" % line_id, 409)
            product_key = pick["product"]["product_key"]
        self.strikes.append({"line_id": line_id, "product_key": product_key, "by": "issuer", "reason": reason,
                             "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")})
        self._state = None
        self.start = self.facts()
        return product_key

    def facts(self) -> dict:
        """What an exact check reads: the hash, what is struck, every limit, the seal, the carts."""
        s = self.get_state()
        return {"sheet_hash": s["sheet_hash"], "signed": s["seal"]["signed"], "carts": len(s["seal"]["carts"]),
                "struck": sorted([k["line_id"], k["product_key"]] for l in s["lines"] for k in l["struck"]),
                "limits": {l["id"]: l["bound"].get("value") for line in s["sheet"]["lines"] for l in line["limits"]},
                "picks": {l["line_id"]: l["pick"] for l in s["lines"]}}

    def changed(self) -> list:
        now, start = self.facts(), self.start or {}
        return [k for k in now if start and now[k] != start.get(k)]
