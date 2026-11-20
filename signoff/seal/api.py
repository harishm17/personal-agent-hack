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
            text = "%s refused: %s" % ((d.get("request") or "request").replace("_", " "), why)
            if out and out[-1].get("whys"):  # refusals that follow each other are one line with a count and the reasons
                last = out[-1]
                last["count"] += 1
                last["whys"] += [why] if why not in last["whys"] else []
                last.update(at=r["at"], text="%d requests refused: %s" % (last["count"], ", ".join(last["whys"])))
            else:
                out.append({"at": r["at"], "from": "agent", "to": "agent", "bad": True, "text": text, "whys": [why], "count": 1})
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
                                "text": "cart lines match the signed picks · %d of %d" % (ok, len(checked))})
    for e in out:
        e.pop("what", None)
        e.pop("whys", None)
        e.pop("count", None)
    return out


def summary(canonical: str, sheet_hash: str | None, name: str | None) -> dict:
    """The one line for every place the signing shows: counted from the canonical sheet itself, with the fingerprint's
    short code (the first twelve hex characters in fours). The phone and the screen can compute the same from their own
    copy of the canonical sheet and its hash; the rule is in NOTES/SCREEN.md and NOTES/SIGN.md."""
    lines = json.loads(canonical)["lines"]
    picks = [l["pick"] for l in lines if l.get("pick")]
    n = {"limits": sum(len(l["limits"]) for l in lines),
         "quotes": sum(len(p["quotes"]) + (1 if p["delivery"].get("quote") else 0) for p in picks),
         "picks": len(picks), "total_cents": json.loads(canonical)["total_cents"]}
    word = lambda k, one: "%d %s" % (n[k], one if n[k] == 1 else one + "s")  # noqa: E731
    return {**n, "code": _short(sheet_hash),
            "text": "%s signs: %s · %s · %s · $%.2f" % (name or "The approver", word("limits", "limit"), word("quotes", "quote"),
                                                        word("picks", "pick"), n["total_cents"] / 100)}


def refused(receipts: list) -> list:
    """Every request the server refused in this run, from the receipt chain: [{n, at, request, why}]."""
    return [{"n": r.get("n"), "at": r["at"], "request": (r.get("detail") or {}).get("request"),
             "why": (r.get("detail") or {}).get("refused_because")}
            for r in receipts if r.get("type") in ("request_refused", "enrolment_refused")]


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
        "summary": summary(canonical, state.get("sheet_hash"), (sheet.get("issuer") or {}).get("name")),
        "signed": bool(seal.get("signed")), "current": seal.get("current") if sig else None,
        "signature": sig and {"payload": sig.get("payload"), "sig": sig.get("sig"), "seq": sig.get("seq"),
                              "sheet_hash": sig.get("sheet_hash"), "at": sig.get("signed_at") or sig.get("at"),
                              "key_id": (sig.get("signer") or {}).get("key_id"), "name": (sig.get("signer") or {}).get("name"),
                              "name_basis": sig.get("name_basis")},
        "public_key": key and {"jwk": key.jwk, "key_id": key.key_id, "name": key.name, "enrolled_at": key.enrolled_at},
        "algorithm": ALGORITHM,
        "identity": {"required": identity_required, **{k: (key.persona if key else {}).get(k) for k in ("status", "verified", "sandbox")}},
        "events": events(receipts, seal), "refused": refused(receipts),
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
