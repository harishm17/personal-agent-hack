"""Reads what Airbyte delivered: the stores' product records and answers in SingleStore (airbyte_pool,
airbyte_store_answers). Never raises; returns None when the tables are missing or empty."""
import json

from signoff.airbyte import export
from signoff.db import conn

META = ("airbyte_job_id", "airbyte_synced_at", "sheet_id")


def _rows(cur, table: str, sheet_id: str) -> list[dict]:
    cur.execute(f"SELECT * FROM {table} WHERE sheet_id = %s ORDER BY store" + (", product_id" if table == "airbyte_pool" else ""),
                (sheet_id,))
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def load(sheet_id: str | None = None) -> dict | None:
    """For the sheet (default: the active sheet). {"via": "airbyte", "job_id", "synced_at", "rows", "pool": [...], "store_answers": [...]}.
    Each pool row has the shape of data/pool/*.json (line_ids is a list)."""
    try:
        sheet_id = sheet_id or export.active_sheet()
        c = conn.connect(timeout=5)
        try:
            cur = c.cursor()
            pool = _rows(cur, "airbyte_pool", sheet_id)
            answers = _rows(cur, "airbyte_store_answers", sheet_id)
        finally:
            c.close()
    except Exception:  # noqa: BLE001
        return None
    if not pool:
        return None
    for r in pool:
        if isinstance(r.get("line_ids"), str):
            r["line_ids"] = json.loads(r["line_ids"])
    first = pool[0]
    return {"via": "airbyte", "sheet_id": sheet_id, "job_id": first.get("airbyte_job_id"),
            "synced_at": str(first.get("airbyte_synced_at")), "rows": len(pool),
            "pool": [{k: v for k, v in r.items() if k not in META} for r in pool],
            "store_answers": [{k: v for k, v in a.items() if k not in META} for a in answers]}
