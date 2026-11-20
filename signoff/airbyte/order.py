"""The therapist's order as Airbyte delivered it (SingleStore table airbyte_order_limits).
Never raises; returns None when the table is missing or empty. These limits are "proposed, from the order"
until the issuer confirms them on her phone."""
from signoff.db import conn


def load() -> dict | None:
    try:
        c = conn.connect(timeout=5)
        try:
            cur = c.cursor()
            cur.execute("SELECT * FROM airbyte_order_limits ORDER BY limit_id")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        finally:
            c.close()
    except Exception:  # noqa: BLE001
        return None
    if not rows:
        return None
    meta = ("airbyte_job_id", "airbyte_synced_at")
    return {"via": "airbyte", "state": "proposed, from the order", "job_id": rows[0]["airbyte_job_id"],
            "synced_at": str(rows[0]["airbyte_synced_at"]), "rows": len(rows),
            "limits": [{k: v for k, v in r.items() if k not in meta} for r in rows]}
