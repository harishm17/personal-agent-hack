"""What the approver's phone does in the browser: an ECDSA P-256 key, a JSON payload string, a raw r||s signature."""
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

from signoff.sign.verify import b64u_encode


class Phone:
    def __init__(self, sheet_id):
        self.private = ec.generate_private_key(ec.SECP256R1())
        n = self.private.public_key().public_numbers()
        self.jwk = {"kty": "EC", "crv": "P-256", "x": b64u_encode(n.x.to_bytes(32, "big")),
                    "y": b64u_encode(n.y.to_bytes(32, "big"))}
        self.sheet_id, self.seq, self.key_id = sheet_id, 0, None

    def request(self, type_, **fields):
        self.seq += 1
        payload = json.dumps({"type": type_, "sheet_id": self.sheet_id, "seq": self.seq, **fields})
        r, s = decode_dss_signature(self.private.sign(payload.encode(), ec.ECDSA(hashes.SHA256())))
        return {"payload": payload, "sig": b64u_encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")), "key_id": self.key_id}
