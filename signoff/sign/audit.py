"""Two one-line helpers every SIGN module uses: a receipt in the engine's chain and a row in the outbound ledger.
Both never raise and never wait, so an audit failure can never stop a signature or a check."""
from __future__ import annotations


def receipt(kind: str, actor: str, key_id=None, body=None, detail=None) -> None:
    try:
        from signoff.engine import receipts
        receipts.append(kind, actor, key_id, body, detail)
    except Exception:  # noqa: BLE001
        pass


def egress(recipient: str, purpose: str, payload=None, fact_classes=None) -> None:
    try:
        from signoff import obs
        obs.egress(recipient, purpose, payload, fact_classes)
    except Exception:  # noqa: BLE001
        pass
