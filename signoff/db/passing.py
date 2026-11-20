"""The passing box as one SQL statement: the candidates of a line that are inside every limit.

Same rules as the engine (CONTRACT.md "Rules code decides"): a figure counts only with its quote found in the
text; a spread uses the end that could fail; an adjustable range passes when the limit lies inside it; a missing
figure fails; a struck product_key is out.
"""
import json

from signoff.db import conn, schema

PASSING_BOX_SQL = """
SELECT p.store, p.product_id, p.title, p.price_cents, p.product_key
FROM pool p
JOIN limits l ON l.line_id = %(line_id)s
LEFT JOIN figures f ON f.store = p.store AND f.product_id = p.product_id
                   AND f.figure = l.figure AND f.span_found_in_text = 1 AND f.unsure = 0
WHERE JSON_ARRAY_CONTAINS_STRING(p.line_ids, %(line_id)s)
  AND p.product_key NOT IN (SELECT product_key FROM strikes WHERE line_id = %(line_id)s)
GROUP BY p.store, p.product_id, p.title, p.price_cents, p.product_key
HAVING MIN(CASE WHEN f.figure IS NULL THEN 0
                WHEN f.kind = 'adjustable' THEN l.shopper_sum + f.low <= l.bound AND l.bound <= l.shopper_sum + f.high
                WHEN l.op = '>=' THEN l.shopper_sum + IF(f.kind = 'spread', f.low, f.value) >= l.bound
                ELSE l.shopper_sum + IF(f.kind = 'spread', f.high, f.value) <= l.bound END) = 1
ORDER BY p.price_cents, p.store, p.product_id
""".strip()


def passing_box(line_id: str) -> dict:
    schema.ensure()
    c = conn.connect()
    try:
        cur = c.cursor()
        cur.execute(PASSING_BOX_SQL, {"line_id": line_id})
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        c.close()
    shown = PASSING_BOX_SQL.replace("%(line_id)s", json.dumps(line_id).replace('"', "'"))
    return {"line_id": line_id, "sql": shown, "rows": rows}
