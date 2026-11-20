"""Tables of database `signoff`. Rowstore: small tables with frequent upserts."""
from signoff.db import conn

TABLES = {
    "pool": """CREATE ROWSTORE TABLE IF NOT EXISTS pool (
        store VARCHAR(80) NOT NULL, product_id VARCHAR(120) NOT NULL, variant_id VARCHAR(120), title VARCHAR(400),
        price_cents INT, url VARCHAR(600), text TEXT, fetched_at VARCHAR(40), product_key VARCHAR(300),
        line_ids JSON, PRIMARY KEY (store, product_id))""",
    # figures as the engine read them; a figure counts only with span_found_in_text = 1
    "figures": """CREATE ROWSTORE TABLE IF NOT EXISTS figures (
        store VARCHAR(80) NOT NULL, product_id VARCHAR(120) NOT NULL, figure VARCHAR(60) NOT NULL,
        kind VARCHAR(20), value DOUBLE, low DOUBLE, high DOUBLE, unit VARCHAR(10), quote TEXT,
        start_pos INT, end_pos INT, extractor VARCHAR(60), span_found_in_text TINYINT,
        PRIMARY KEY (store, product_id, figure))""",
    # one row per limit of the current state: shopper_sum is the sum of the shopper-fact terms, bound is resolved
    "limits": """CREATE ROWSTORE TABLE IF NOT EXISTS limits (
        limit_id VARCHAR(40) NOT NULL PRIMARY KEY, line_id VARCHAR(20), name VARCHAR(80), op VARCHAR(2),
        figure VARCHAR(60), shopper_sum DOUBLE, bound DOUBLE, unit VARCHAR(10), state_version INT)""",
    "strikes": """CREATE ROWSTORE TABLE IF NOT EXISTS strikes (
        line_id VARCHAR(20) NOT NULL, product_key VARCHAR(300) NOT NULL, reason TEXT,
        PRIMARY KEY (line_id, product_key))""",
    # the decision record: one row per candidate per state version
    "decisions": """CREATE ROWSTORE TABLE IF NOT EXISTS decisions (
        state_version INT NOT NULL, candidate_id VARCHAR(300) NOT NULL, line_id VARCHAR(20), store VARCHAR(80),
        product_id VARCHAR(120), product_key VARCHAR(300), status VARCHAR(20), reason TEXT, picked TINYINT,
        price_cents INT, record JSON, written_at DATETIME DEFAULT NOW(),
        PRIMARY KEY (state_version, candidate_id))""",
    "meta": "CREATE ROWSTORE TABLE IF NOT EXISTS meta (k VARCHAR(40) PRIMARY KEY, v VARCHAR(200))",
}


_done: set = set()


def ensure() -> None:
    if conn.DB in _done:
        return
    root = conn.connect(database=None)
    try:
        cur = root.cursor()
        cur.execute("CREATE DATABASE IF NOT EXISTS " + conn.DB)
    finally:
        root.close()
    c = conn.connect()
    try:
        cur = c.cursor()
        for ddl in TABLES.values():
            cur.execute(ddl)
    finally:
        c.close()
    _done.add(conn.DB)
