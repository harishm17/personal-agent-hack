"""The signature page's check, on a real saved signature: `proof-signed.json` is `GET /api/seal/proof` from a run on
the TALK dev port (20 Nov 14:38, sheet 4, replay mode; the key was made and the message signed by demo/signer.py, the
identity inquiry is a Persona sandbox one). Nothing in these files was written by hand."""
import hashlib
import json
import pathlib
import shutil
import subprocess

import pytest

from signoff.seal import api
from signoff.sign import verify

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent


@pytest.fixture
def proof():
    return json.loads((HERE / "proof-signed.json").read_text())


def test_the_saved_signature_verifies_and_names_the_fingerprint_of_the_canonical_bytes(proof):
    s = proof["signature"]
    message = json.loads(s["payload"])
    assert message["type"] == "sign_sheet" and message["seq"] == s["seq"] and message["sheet_id"] == proof["sheet"]["id"]
    assert hashlib.sha256(proof["canonical"].encode()).hexdigest() == message["sheet_hash"] == proof["sheet_hash"]
    verify.check_signature(proof["public_key"]["jwk"], s["payload"], s["sig"])  # raises Refused if it does not verify
    assert verify.key_id_for(proof["public_key"]["jwk"]) == s["key_id"]


def test_a_one_character_change_fails(proof):
    s, jwk = proof["signature"], proof["public_key"]["jwk"]
    at = proof["canonical"].index('"bound":300') + len('"bound":')
    changed = proof["canonical"][:at] + "2" + proof["canonical"][at + 1:]
    assert len(changed) == len(proof["canonical"]) and sum(a != b for a, b in zip(changed, proof["canonical"])) == 1
    new_hash = hashlib.sha256(changed.encode()).hexdigest()
    assert new_hash != json.loads(s["payload"])["sheet_hash"]
    with pytest.raises(verify.Refused):  # the message that would name the changed sheet was never signed
        verify.check_signature(jwk, s["payload"].replace(proof["sheet_hash"], new_hash), s["sig"])
    with pytest.raises(verify.Refused):  # nor is the message itself signed if one character of it changes
        verify.check_signature(jwk, s["payload"].replace('"seq": %d' % s["seq"], '"seq": %d' % (s["seq"] + 1)), s["sig"])


def test_the_pages_own_code_agrees(proof):
    """web/seal/verify.js, the file the browser loads, run by node on the same proof."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed: the browser's check was not run here")
    done = subprocess.run([node, str(HERE / "check.mjs"), str(ROOT / "web" / "seal" / "verify.js"), str(HERE / "proof-signed.json")],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    out = json.loads(done.stdout)
    assert out["real"]["fingerprint"] == proof["sheet_hash"] == out["real"]["signedFingerprint"]
    assert out["real"]["messageVerifies"] is True and out["real"]["coversThis"] is True and out["real"]["valid"] is True
    assert out["firstBound"] == "300" and out["same"] is True
    assert out["oneChar"]["fingerprint"] != proof["sheet_hash"] and out["oneChar"]["messageVerifies"] is True
    assert out["oneChar"]["coversThis"] is False and out["oneChar"]["valid"] is False
    assert out["roundTrip"] is False  # why the page edits the text in place: a re-serialised copy is not the signed bytes
    assert out["quote"] == json.dumps('1–5 days "x"')


def test_unsigned_proof_has_no_signature_and_no_cart():
    p = json.loads((HERE / "proof-unsigned.json").read_text())
    assert p["signed"] is False and p["signature"] is None and p["public_key"] is None and p["carts"] == []
    assert hashlib.sha256(p["canonical"].encode()).hexdigest() == p["sheet_hash"]


def test_events_follow_the_receipts_in_order(proof):
    """The saved run: enrolled, two signed limit changes, a signing refused for identity, a sandbox identity inquiry,
    the signature, three replay carts, then the page's four attempts made by Chrome, all refused."""
    texts = [e["text"] for e in proof["events"]]
    assert texts[0] == "public key enrolled with a one-time code" and "2 signed limit changes" in texts
    assert texts.index("verified with the public key") < texts.index("3 carts created · replay") < texts.index("cart lines match the signed picks · 3 of 3")
    bad = [e["text"] for e in proof["events"] if e.get("bad")]
    assert bad and all(" refused: " in t for t in bad) and any("replayed seq" in t for t in bad)
    assert len(proof["refused"]) >= 4 and {r["request"] for r in proof["refused"]} == {"sign_sheet", "set_limit"}
    assert proof["signed"] is True and proof["current"] is True  # after the refused attempts the seal is as it was
    assert all(e["from"] in api.LANES and e["to"] in api.LANES for e in proof["events"])
    assert api.events([], {}) == []


def test_the_one_line_is_counted_from_the_canonical_sheet(proof):
    s = api.summary(proof["canonical"], proof["sheet_hash"], "Dana")
    sheet = json.loads(proof["canonical"])
    assert s["limits"] == sum(len(l["limits"]) for l in sheet["lines"]) == 6 and s["picks"] == 3 and s["quotes"] == 8
    assert s["text"] == "Dana signs: 6 limits · 8 quotes · 3 picks · $114.69" and s["code"] == "3ac9 4ba1 dd01"
    assert s["code"].replace(" ", "") == proof["sheet_hash"][:12]


# ---- K6: the four attempts the page makes, against SIGN's own check (no server, no network) ----

def _signed(key, payload: dict) -> dict:
    import base64
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    text = json.dumps(payload)
    r, s = decode_dss_signature(key.sign(text.encode(), ec.ECDSA(hashes.SHA256())))
    return {"payload": text, "sig": base64.urlsafe_b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).rstrip(b"=").decode()}


def _jwk(key) -> dict:
    n = key.public_key().public_numbers()
    return {"kty": "EC", "crv": "P-256", "x": verify.b64u_encode(n.x.to_bytes(32, "big")), "y": verify.b64u_encode(n.y.to_bytes(32, "big"))}


def test_each_attempt_without_her_key_is_refused_and_changes_nothing():
    from cryptography.hazmat.primitives.asymmetric import ec
    hers, other = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
    store = verify.KeyStore(path=None)
    enrolled = store.enroll(_jwk(hers), "Dana", "2026-11-20T15:00:00-08:00", store.code)
    real = {**_signed(hers, {"type": "sign_sheet", "sheet_id": "sheet4", "seq": 4, "sheet_hash": "h"}), "key_id": enrolled.key_id}
    assert verify.verify_request(store, real, "sheet4", "h")["seq"] == 4 and store.key.last_seq == 4
    late = {"type": "sign_sheet", "sheet_id": "sheet4", "seq": 10 ** 13, "sheet_hash": "h"}
    attempts = {
        "no signature": ({"payload": json.dumps(late), "key_id": enrolled.key_id}, "unsigned", 401),
        "a key that was never enrolled, claiming to be hers": ({**_signed(other, late), "key_id": enrolled.key_id}, "unsigned", 401),
        "a key that was never enrolled, under its own id": ({**_signed(other, late), "key_id": verify.key_id_for(_jwk(other))}, "unsigned", 401),
        "her signed request again": (real, "replayed_seq", 409),
        "a limit change with no signature": ({"payload": json.dumps({"type": "set_limit", "sheet_id": "sheet4", "seq": 10 ** 13,
                                                                    "limit_id": "L1.capacity", "value": 250}), "key_id": enrolled.key_id}, "unsigned", 401),
    }
    for name, (body, code, status) in attempts.items():
        with pytest.raises(verify.Refused) as refusal:
            verify.verify_request(store, body, "sheet4", "h")
        assert (refusal.value.code, refusal.value.status) == (code, status), name
        assert store.key.key_id == enrolled.key_id and store.key.last_seq == 4, name  # the key and seq are as they were


def test_refused_requests_are_listed_from_the_receipts():
    chain = [{"n": 1, "at": "t1", "type": "enrolled", "detail": {}},
             {"n": 2, "at": "t2", "type": "request_refused", "detail": {"request": "sign_sheet", "refused_because": "unsigned: x"}},
             {"n": 3, "at": "t3", "type": "request_refused", "detail": {"request": "sign_sheet", "refused_because": "unsigned: x"}}]
    assert [(r["n"], r["request"]) for r in api.refused(chain)] == [(2, "sign_sheet"), (3, "sign_sheet")]
    assert [e["text"] for e in api.events(chain, {})][-1] == "2 requests refused: unsigned"
    assert [e["text"] for e in api.events(chain[:2], {})][-1] == "sign sheet refused: unsigned"
