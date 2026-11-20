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
        verify.check_signature(jwk, s["payload"].replace('"seq": 4', '"seq": 5'), s["sig"])


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
    texts = [e["text"] for e in proof["events"]]
    assert texts[0] == "public key enrolled with a one-time code" and "2 signed limit changes" in texts
    assert [e["text"] for e in proof["events"] if e.get("bad")] == ["sign sheet refused: identity not verified"]
    assert texts.index("verified with the public key") < texts.index("3 carts created · replay") < len(texts) - 1
    assert texts[-1].startswith("cart lines ") and "3 of 3" in texts[-1]
    assert all(e["from"] in api.LANES and e["to"] in api.LANES for e in proof["events"])
    assert api.events([], {}) == []


def test_the_one_line_is_counted_from_the_canonical_sheet(proof):
    s = api.summary(proof["canonical"], proof["sheet_hash"], "Dana")
    sheet = json.loads(proof["canonical"])
    assert s["limits"] == sum(len(l["limits"]) for l in sheet["lines"]) == 6 and s["picks"] == 3 and s["quotes"] == 8
    assert s["text"] == "Dana signs: 6 limits · 8 quotes · 3 picks · $114.69" and s["code"] == "3ac9 4ba1 dd01"
    assert s["code"].replace(" ", "") == proof["sheet_hash"][:12]
