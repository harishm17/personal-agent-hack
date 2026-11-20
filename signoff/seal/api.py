"""GET /api/seal/proof: everything a browser needs to check the approver's signature for itself, and the run's signing
events in order. Read-only, composed from what ENGINE and SIGN already hold; nothing here writes state.

How the signature works (signoff/sign/verify.py, web/phone/index.html, signoff/engine/state.py):
- the fingerprint is the SHA-256, in hex, of the UTF-8 bytes of the canonical sheet (`canonical`, exactly as given here);
- the phone signs a message, not the bare fingerprint: the JSON string `payload`, which names `type: "sign_sheet"`, the
  sheet id, `seq`, the phone's time and `sheet_hash` (the fingerprint the phone computed from the sheet it displayed);
- the signature is ECDSA P-256 with SHA-256 over the UTF-8 bytes of `payload`, raw r||s (64 bytes), base64url;
- the server holds only the public key (JWK), enrolled once with a one-time code.
"""
import json

from fastapi import APIRouter

router = APIRouter()
LANES = ("phone", "agent", "stores")
ALGORITHM = {"signature": "ECDSA P-256, SHA-256, raw r||s (64 bytes), base64url",
             "message": "the UTF-8 bytes of signature.payload",
             "fingerprint": "SHA-256 (hex) of the UTF-8 bytes of canonical; the message names it as sheet_hash"}


def _short(sheet_hash: str | None) -> str:
    h = (sheet_hash or "")[:12]
    return " ".join(h[i:i + 4] for i in range(0, len(h), 4))


def events(receipts: list, seal: dict) -> list:
    """The signing events of the run, in order: [{at, from, to, text, bad?}]. `from` and `to` are lanes; equal lanes mean
    the event happens in one place. Signed limit changes that follow each other are one event with a count."""
    out, sig = [], (seal or {}).get("signature") or {}
    for r in receipts:
        d, kind = r.get("detail") or {}, r.get("type")
        if kind == "enrolled":
            out.append({"at": r["at"], "from": "phone", "to": "agent", "text": "public key enrolled with a one-time code"})
        elif kind == "persona_status":
            out.append({"at": r["at"], "from": "phone", "to": "phone",
                        "text": "identity inquiry %s%s" % (d.get("status") or "", " · sandbox" if d.get("sandbox") else "")})
        elif kind == "request_accepted" and d.get("request") not in (None, "sign_sheet"):
            what = {"set_limit": "signed limit change", "strike": "signed strike", "unstrike": "signed unstrike"}.get(d["request"], "signed " + d["request"])
            if out and out[-1].get("what") == what:
                out[-1]["count"] += 1
                out[-1]["text"] = "%d %ss" % (out[-1]["count"], what)
                out[-1]["at"] = r["at"]
            else:
                out.append({"at": r["at"], "from": "phone", "to": "agent", "text": what, "what": what, "count": 1})
        elif kind == "request_refused":
            why = str(d.get("refused_because") or "").split(":")[0].replace("_", " ")
            out.append({"at": r["at"], "from": "agent", "to": "agent", "bad": True,
                        "text": "%s refused: %s" % ((d.get("request") or "request").replace("_", " "), why)})
        elif kind == "request_accepted" and d.get("request") == "sign_sheet":
            sent = None
            try:
                sent = json.loads(sig.get("payload") or "{}").get("at") if sig.get("seq") == d.get("seq") else None
            except ValueError:
                pass
            out.append({"at": sent or r["at"], "from": "phone", "to": "agent",
                        "text": "signature over %s · seq %s" % (_short(d.get("sheet_hash")), d.get("seq"))})
            out.append({"at": r["at"], "from": "agent", "to": "agent", "text": "verified with the public key"})
            carts = [c for c in (seal or {}).get("carts", []) if c.get("cart_url") or c.get("cart_id")]
            if carts:
                replay = all(c.get("mode") == "replay" for c in carts)
                out.append({"at": carts[0].get("created_at") or r["at"], "from": "agent", "to": "stores",
                            "text": "%d cart%s created%s" % (len(carts), "" if len(carts) == 1 else "s", " · replay" if replay else "")})
                checked = [c for c in carts if "lines_checked" in c]
                if checked:
                    ok = sum(1 for c in checked if c["lines_checked"])
                    out.append({"at": carts[0].get("created_at") or r["at"], "from": "stores", "to": "agent", "bad": ok < len(checked),
                                "text": "cart lines compared with the signed picks · %d of %d match" % (ok, len(checked))})
    for e in out:
        e.pop("what", None)
        e.pop("count", None)
    return out


def compose(state: dict, canonical: str, key, receipts: list, identity_required: bool) -> dict:
    """The proof from the engine's state, the canonical sheet, SIGN's enrolled key (or None) and the receipt chain."""
    seal, sheet = state.get("seal") or {}, state["sheet"]
    sig = seal.get("signature") or None
    return {
        "sheet": {"id": sheet["id"], "title": sheet.get("title"), "invented": bool(sheet.get("invented"))},
        "approver": {"name": (sheet.get("issuer") or {}).get("name"), "role": (sheet.get("issuer") or {}).get("role_label")},
        "shopper": {"name": (sheet.get("shopper") or {}).get("name")},
        "mode": state.get("mode"),
        "canonical": canonical, "sheet_hash": state.get("sheet_hash"), "covers": seal.get("covers") or [],
        "signed": bool(seal.get("signed")), "current": seal.get("current") if sig else None,
        "signature": sig and {"payload": sig.get("payload"), "sig": sig.get("sig"), "seq": sig.get("seq"),
                              "sheet_hash": sig.get("sheet_hash"), "at": sig.get("signed_at") or sig.get("at"),
                              "key_id": (sig.get("signer") or {}).get("key_id"), "name": (sig.get("signer") or {}).get("name"),
                              "name_basis": sig.get("name_basis")},
        "public_key": key and {"jwk": key.jwk, "key_id": key.key_id, "name": key.name, "enrolled_at": key.enrolled_at},
        "algorithm": ALGORITHM,
        "identity": {"required": identity_required, **{k: (key.persona if key else {}).get(k) for k in ("status", "verified", "sandbox")}},
        "events": events(receipts, seal),
        "carts": [{"store": c.get("store"), "total_cents": c.get("total_cents"), "signed_total_cents": c.get("signed_total_cents"),
                   "lines": len(c.get("lines") or []), "lines_checked": c.get("lines_checked"), "mode": c.get("mode")}
                  for c in seal.get("carts", [])],
    }


@router.get("/api/seal/proof")
def proof():
    from signoff.engine import receipts
    from signoff.engine import state as engine
    from signoff.sign import api as sign
    state = engine.get_state()
    return compose(state, engine.canonical_sheet(), sign.keystore.key, receipts.chain()["receipts"], sign.identity_required())
