"""Plays the approver's phone from the laptop, for rehearsing the big screen without a phone: enrols a fresh P-256 key
with the laptop's one-time code, then sends signed requests exactly as web/phone does (ECDSA over the payload's bytes,
raw r||s, base64url). Use it against your own dev port, in replay mode, never against main during the demo.

  uv run python demo/signer.py --base http://localhost:8003 enrol
  uv run python demo/signer.py --base http://localhost:8003 limit L5.length 24 [--after 3]
  uv run python demo/signer.py --base http://localhost:8003 strike L5 [--after 3]      (strikes the current pick)
  uv run python demo/signer.py --base http://localhost:8003 sign [--after 3]
  uv run python demo/signer.py --base http://localhost:8003 reset
The key is kept in the scratch file given by --key (default: demo/shots/signer-key.json, not committed).
"""
import argparse
import base64
import datetime
import json
import pathlib
import time

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def load_key(path):
    data = json.loads(path.read_text())
    return serialization.load_pem_private_key(data["pem"].encode(), None), data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8003")
    ap.add_argument("--key", default="demo/shots/signer-key.json")
    ap.add_argument("--after", type=float, default=0, help="seconds to wait before sending")
    ap.add_argument("what", choices=["enrol", "limit", "strike", "sign", "reset"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    path, http = pathlib.Path(a.key), httpx.Client(base_url=a.base, timeout=60)
    if a.what == "reset":
        print(http.post("/api/admin/reset").status_code)
        return
    if a.what == "enrol":
        key = ec.generate_private_key(ec.SECP256R1())
        n = key.public_key().public_numbers()
        jwk = {"kty": "EC", "crv": "P-256", "x": b64(n.x.to_bytes(32, "big")), "y": b64(n.y.to_bytes(32, "big"))}
        code = http.get("/api/issuer/enroll-code").json()["code"]
        name = http.get("/api/state").json()["sheet"]["issuer"]["name"]
        out = http.post("/api/issuer/enroll", json={"public_key_jwk": jwk, "name": name, "code": code}).json()
        if not out.get("ok"):
            print(out)          # a key is already enrolled: `reset` first; the saved key is left as it was
            return
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"pem": pem, "key_id": out.get("key_id"), "seq": 0}))
        print(out)
        return
    key, data = load_key(path)
    time.sleep(a.after)
    state = http.get("/api/state").json()
    data["seq"] += 1
    payload = {"sheet_id": state["sheet"]["id"], "seq": data["seq"], "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    if a.what == "limit":
        payload.update(type="set_limit", limit_id=a.args[0], value=float(a.args[1]))
    elif a.what == "strike":
        line = next(l for l in state["lines"] if l["line_id"] == a.args[0])
        pick = next(c for c in line["candidates"] if c["picked"])
        payload.update(type="strike", line_id=line["line_id"], product_key=pick["product"]["product_key"], reason="rehearsal strike from demo/signer.py")
    else:
        payload.update(type="sign_sheet", sheet_hash=http.get("/api/sheet/canonical").json()["sheet_hash"])
    text = json.dumps(payload)
    r, s = decode_dss_signature(key.sign(text.encode(), ec.ECDSA(hashes.SHA256())))
    res = http.post("/api/issuer/request", json={"payload": text, "sig": b64(r.to_bytes(32, "big") + s.to_bytes(32, "big")), "key_id": data["key_id"]})
    path.write_text(json.dumps(data))
    print(res.status_code, json.dumps(res.json())[:400])


if __name__ == "__main__":
    main()
