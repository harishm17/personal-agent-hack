"""The passing box as one SQL statement: the candidates of a line that are inside every limit.

It is the engine's rule (signoff/engine/rules.py `check`) written a second time, in SQL, over the tables records.write fills:
  - a candidate is one row of `pool` (a product sold in several options is several candidates);
  - every statement the page makes for a figure is a row of `figures`; a statement counts if its quote was found in the text
    and (when known) holds a number; a statement is comparable if it has numbers, is in the limit's unit and is not for another
    option; no statement at all, or none comparable, is not inside;
  - every value stated is tested: a single number is one value, a spread is its two ends, a range the user can set is the
    setting that best meets the comparison; the candidate is inside only if every tested value passes (`several` "largest" or
    "smallest" tests only that one value); `==` needs the value to equal the bound; a struck product_key is out.
"""
import json

from signoff.db import conn, schema


def _holds(x: str, p: str = "r") -> str:
    return (f"CASE WHEN {p}.op = '==' THEN ABS(({x}) - {p}.bound) < 1e-9 WHEN {p}.op = '>=' THEN ({x}) >= {p}.bound "
            f"ELSE ({x}) <= {p}.bound END")


PASSING_BOX_SQL = f"""
SELECT m.cand_id, m.store, m.product_id, m.variant_id, m.title, m.price_cents, m.product_key
FROM (
  SELECT r.cand_id, r.store, r.product_id, r.variant_id, r.title, r.price_cents, r.product_key, r.limit_id,
    CASE WHEN SUM(r.stated) = 0 THEN 0
         WHEN SUM(r.usable) = 0 THEN 0
         WHEN r.several = 'largest' THEN {_holds("r.shopper_sum + MAX(CASE WHEN r.usable = 1 THEN GREATEST(r.v1, IFNULL(r.v2, r.v1)) END)")}
         WHEN r.several = 'smallest' THEN {_holds("r.shopper_sum + MIN(CASE WHEN r.usable = 1 THEN LEAST(r.v1, IFNULL(r.v2, r.v1)) END)")}
         ELSE MIN(CASE WHEN r.usable = 1 THEN ({_holds("r.shopper_sum + r.v1")}) AND (r.v2 IS NULL OR ({_holds("r.shopper_sum + r.v2")})) END)
    END AS passed
  FROM (
    SELECT c.cand_id, c.store, c.product_id, c.variant_id, c.title, c.price_cents, c.product_key,
      l.limit_id, l.op, l.bound, l.shopper_sum, l.several,
      IF(f.cand_id IS NOT NULL AND f.span_found_in_text = 1 AND (f.number_in_quote IS NULL OR f.number_in_quote = 1), 1, 0) AS stated,
      IF(f.cand_id IS NOT NULL AND f.span_found_in_text = 1 AND (f.number_in_quote IS NULL OR f.number_in_quote = 1)
         AND f.unit = l.unit AND f.for_other_option IS NULL
         AND ((f.kind = 'single' AND f.value IS NOT NULL) OR (f.kind IN ('spread', 'adjustable') AND f.low IS NOT NULL AND f.high IS NOT NULL)),
         1, 0) AS usable,
      CASE f.kind WHEN 'single' THEN f.value WHEN 'spread' THEN f.low
        WHEN 'adjustable' THEN CASE l.op WHEN '>=' THEN f.high WHEN '<=' THEN f.low
          ELSE CASE WHEN f.low <= l.bound - l.shopper_sum AND l.bound - l.shopper_sum <= f.high THEN l.bound - l.shopper_sum
                    WHEN ABS(f.low - (l.bound - l.shopper_sum)) <= ABS(f.high - (l.bound - l.shopper_sum)) THEN f.low
                    ELSE f.high END END END AS v1,
      CASE f.kind WHEN 'spread' THEN f.high END AS v2
    FROM {{pool_table}} c
    JOIN limits l ON l.line_id = c.line_id
    LEFT JOIN figures f ON f.cand_id = c.cand_id AND f.figure = l.figure
    WHERE c.line_id = %(line_id)s{{airbyte_filter}}
      AND c.product_key NOT IN (SELECT product_key FROM strikes WHERE line_id = %(line_id)s)
  ) r
  GROUP BY r.cand_id, r.store, r.product_id, r.variant_id, r.title, r.price_cents, r.product_key, r.limit_id,
           r.op, r.bound, r.shopper_sum, r.several
) m
GROUP BY m.cand_id, m.store, m.product_id, m.variant_id, m.title, m.price_cents, m.product_key
HAVING MIN(m.passed) = 1 AND COUNT(*) = (SELECT COUNT(*) FROM limits WHERE line_id = %(line_id)s)
ORDER BY m.price_cents, m.store, m.cand_id
""".strip()

AIRBYTE = "signoff.airbyte_pool"  # Airbyte's delivery lives in the app database, whatever database this process is using
AIRBYTE_FILTER = f"\n      AND CONCAT(c.store, '|', c.product_id) IN (SELECT CONCAT(store, '|', product_id) FROM {AIRBYTE})"


def _sql(airbyte: bool = False) -> str:
    return PASSING_BOX_SQL.replace("{pool_table}", "pool").replace("{airbyte_filter}", AIRBYTE_FILTER if airbyte else "")


def _run(cur, line_id: str, airbyte: bool = False) -> list[dict]:
    cur.execute(_sql(airbyte), {"line_id": line_id})
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def passing_box(line_id: str, source: str = "direct") -> dict:
    """Runs the statement on the app's candidates (source "direct"), or only on the products Airbyte delivered to `airbyte_pool`
    (the same statement, its candidates restricted to the products in that table), and in that case also directly, and says whether
    the two answers are the same set of products. The limits and figures are the app's own in both runs."""
    schema.ensure()
    c = conn.connect()
    try:
        cur = c.cursor()
        direct = _run(cur, line_id)
        out = {"line_id": line_id, "source": source}
        if source == "airbyte":
            try:
                rows = _run(cur, line_id, airbyte=True)
                cur.execute("SELECT COUNT(*), MIN(airbyte_synced_at), MAX(airbyte_synced_at), COUNT(DISTINCT airbyte_job_id) FROM " + AIRBYTE)
                n, first, last, jobs = cur.fetchone()
                cur.execute("SELECT COUNT(DISTINCT CONCAT(c.store, '|', c.product_id)) FROM pool c WHERE CONCAT(c.store, '|', c.product_id) IN "
                            "(SELECT CONCAT(store, '|', product_id) FROM " + AIRBYTE + ")")
                overlap = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT CONCAT(store, '|', product_id)) FROM pool")
                direct_n = cur.fetchone()[0]
            except Exception as e:  # noqa: BLE001
                raise RuntimeError("airbyte_pool unavailable: " + type(e).__name__)
            key = lambda r: (r["store"], r["product_id"])  # noqa: E731
            a, d = {key(r) for r in rows}, {key(r) for r in direct}
            out.update(rows=rows, direct_rows=direct, same=a == d, only_in_airbyte=sorted(a - d), only_in_direct=sorted(d - a),
                       airbyte={"rows": n, "jobs": jobs, "first_synced_at": str(first), "last_synced_at": str(last),
                                "products_also_in_the_app": overlap, "app_products": direct_n,
                                "note": "Airbyte delivered these rows at the times shown; products added to the pool since are not in it until the next sync, "
                                        "so the direct answer can hold products the delivered rows do not."})
        else:
            out["rows"] = direct
    finally:
        c.close()
    out["sql"] = _sql(source == "airbyte").replace("%(line_id)s", json.dumps(line_id).replace('"', "'"))
    return out
