"""Tables of database `signoff`. Rowstore: small tables with frequent upserts."""
from signoff.db import conn

SCHEMA_VERSION = "3"  # 3: one row per candidate (an option is its own candidate), every stated value of a figure is a row

TABLES = {
    # one row per candidate of the engine's state (a product sold in several options is several candidates)
    "pool": """CREATE ROWSTORE TABLE IF NOT EXISTS pool (
        cand_id VARCHAR(400) NOT NULL PRIMARY KEY, line_id VARCHAR(20), store VARCHAR(80) NOT NULL,
        product_id VARCHAR(120) NOT NULL, variant_id VARCHAR(120), title VARCHAR(400), price_cents INT,
        product_key VARCHAR(300), url VARCHAR(600))""",
    # every statement of a figure as the engine holds it for the candidate (several per figure when the page states several)
    "figures": """CREATE ROWSTORE TABLE IF NOT EXISTS figures (
        cand_id VARCHAR(400) NOT NULL, figure VARCHAR(60) NOT NULL, idx INT NOT NULL,
        kind VARCHAR(20), value DOUBLE, low DOUBLE, high DOUBLE, unit VARCHAR(20), quote TEXT,
        start_pos INT, end_pos INT, extractor VARCHAR(60), span_found_in_text TINYINT, unsure TINYINT DEFAULT 0,
        number_in_quote TINYINT, for_other_option VARCHAR(200), PRIMARY KEY (cand_id, figure, idx))""",
    # one row per limit of the current state: shopper_sum is the sum of the shopper-fact terms, bound is resolved
    "limits": """CREATE ROWSTORE TABLE IF NOT EXISTS limits (
        limit_id VARCHAR(40) NOT NULL PRIMARY KEY, line_id VARCHAR(20), name VARCHAR(80), op VARCHAR(2),
        figure VARCHAR(60), shopper_sum DOUBLE, bound DOUBLE, unit VARCHAR(20), several VARCHAR(10), state_version INT)""",
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
        cur.execute(TABLES["meta"])
        cur.execute("SELECT v FROM meta WHERE k = 'schema_version'")
        row = cur.fetchone()
        if not row or row[0] != SCHEMA_VERSION:  # tables of an older layout: drop the three that changed (they are rewritten on every state)
            for t in ("pool", "figures", "limits"):
                cur.execute("DROP TABLE IF EXISTS " + t)
        for ddl in TABLES.values():
            cur.execute(ddl)
        cur.execute("REPLACE INTO meta (k, v) VALUES ('schema_version', %s)", (SCHEMA_VERSION,))
    finally:
        c.close()
    _done.add(conn.DB)
