"""The passing box as one SQL statement: the candidates of a line that are inside every limit.

Same rules as the engine (CONTRACT.md "Rules code decides"): a figure counts only with its quote found in the
text; a spread uses the end that could fail; an adjustable range passes when the limit lies inside it; a missing
figure fails; a figure in another unit than the limit fails; `==` needs the figure to equal the bound (a range passes when the
bound lies inside it); a struck product_key is out.
"""
import json

from signoff.db import conn, schema

PASSING_BOX_SQL = """
SELECT p.store, p.product_id, p.title, p.price_cents, p.product_key
FROM {pool_table} p
JOIN limits l ON l.line_id = %(line_id)s
LEFT JOIN figures f ON f.store = p.store AND f.product_id = p.product_id
                   AND f.figure = l.figure AND f.span_found_in_text = 1 AND f.unsure = 0
WHERE JSON_ARRAY_CONTAINS_STRING(p.line_ids, %(line_id)s)
  AND p.product_key NOT IN (SELECT product_key FROM strikes WHERE line_id = %(line_id)s)
GROUP BY p.store, p.product_id, p.title, p.price_cents, p.product_key
HAVING MIN(CASE WHEN f.figure IS NULL THEN 0
                WHEN f.unit <> l.unit THEN 0
                WHEN f.kind = 'adjustable' OR (l.op = '==' AND f.kind = 'spread')
                     THEN l.shopper_sum + f.low <= l.bound + 1e-9 AND l.bound <= l.shopper_sum + f.high + 1e-9
                WHEN l.op = '==' THEN ABS(l.shopper_sum + f.value - l.bound) < 1e-9
                WHEN l.op = '>=' THEN l.shopper_sum + IF(f.kind = 'spread', f.low, f.value) >= l.bound
                ELSE l.shopper_sum + IF(f.kind = 'spread', f.high, f.value) <= l.bound END) = 1
ORDER BY p.price_cents, p.store, p.product_id
""".strip()


AIRBYTE = "signoff.airbyte_pool"  # Airbyte's delivery lives in the app database, whatever database this process is using


def _run(cur, line_id: str, table: str) -> list[dict]:
    cur.execute(PASSING_BOX_SQL.replace("{pool_table}", table), {"line_id": line_id})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def passing_box(line_id: str, source: str = "direct") -> dict:
    """Runs the statement on the app's own pool table (source "direct"), or on `airbyte_pool`, the rows Airbyte delivered to
    SingleStore (same columns), and in that case also on the direct table, and says whether the two answers are the same.
    The limits and figures are the app's own in both runs: only the product rows differ."""
    schema.ensure()
    c = conn.connect()
    try:
        cur = c.cursor()
        direct = _run(cur, line_id, "pool")
        out = {"line_id": line_id, "source": source}
        if source == "airbyte":
            try:
                rows = _run(cur, line_id, AIRBYTE)
                cur.execute("SELECT COUNT(*), MIN(airbyte_synced_at), MAX(airbyte_synced_at), COUNT(DISTINCT airbyte_job_id) FROM " + AIRBYTE)
                n, first, last, jobs = cur.fetchone()
                cur.execute("SELECT COUNT(*) FROM " + AIRBYTE + " a JOIN pool p ON p.store = a.store AND p.product_id = a.product_id")
                overlap = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM pool")
                direct_n = cur.fetchone()[0]
            except Exception as e:  # noqa: BLE001
                raise RuntimeError("airbyte_pool unavailable: " + type(e).__name__)
            key = lambda r: (r["store"], r["product_id"])  # noqa: E731
            a, d = {key(r) for r in rows}, {key(r) for r in direct}
            out.update(rows=rows, direct_rows=direct, same=a == d,
                       only_in_airbyte=sorted(a - d), only_in_direct=sorted(d - a),
                       airbyte={"rows": n, "jobs": jobs, "first_synced_at": str(first), "last_synced_at": str(last),
                                "rows_also_in_the_app_pool": overlap, "app_pool_rows": direct_n,
                                "note": "Airbyte delivered these rows at the times shown; products added to the pool since are not in it until the next sync."})
        else:
            out["rows"] = direct
    finally:
        c.close()
    out["sql"] = PASSING_BOX_SQL.replace("{pool_table}", AIRBYTE if source == "airbyte" else "pool").replace(
        "%(line_id)s", json.dumps(line_id).replace('"', "'"))
    return out
