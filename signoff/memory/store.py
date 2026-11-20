"""The memory store: one row per memory, in SingleStore (table `memory`) and in a local JSON-lines mirror.

A row is `{id, owner, kind, key, value, text, source, created_at, sheet_id}` (+ `owner_id`, `owner_name`).
`write()` is the only way in, and it accepts a row only when the record its `source` names proves exactly that
row. A row that reached a table some other way is never recalled: every read is checked against the records again.
"""
import datetime
import json
import os
import pathlib
import threading
import time

from signoff.memory import sources
from signoff.memory.sources import Refused

ROOT = sources.ROOT
OWNED = ("owner", "kind", "key", "value", "text", "sheet_id", "created_at")
_lock = threading.RLock()
_db = {"conn": None, "ready": set(), "state": "not tried", "error": None}


def folder() -> pathlib.Path:
    return pathlib.Path(os.environ.get("SIGNOFF_MEMORY_DIR") or ROOT / "data" / "memory")


def mirror_file() -> pathlib.Path:
    return folder() / "memory.jsonl"


def table() -> str:
    name = os.environ.get("SIGNOFF_MEMORY_TABLE") or "memory"
    if not name.replace("_", "").isalnum():
        raise ValueError("table name must be letters, digits and underscores")
    return name


# --- the mirror -------------------------------------------------------------------------------------------------

def mirror_rows() -> list:
    rows = sources._cached(mirror_file(), sources._jsonl)
    return list(rows or [])


def _mirror_add(rows) -> int:
    with _lock:
        have = {r.get("id") for r in mirror_rows()}
        new = [r for r in rows if r["id"] not in have]
        if new:
            folder().mkdir(parents=True, exist_ok=True)
            with open(mirror_file(), "a") as f:
                for row in new:
                    f.write(sources.receipts.canonical(row) + "\n")
        return len(new)


# --- SingleStore ------------------------------------------------------------------------------------------------

def db_off() -> bool:
    return (os.environ.get("SIGNOFF_MEMORY_DB") or "").lower() == "off"


def _connect():
    """One kept connection, made on first use. Raises when the database cannot be reached."""
    from signoff.db import conn as dbconn
    if _db["conn"] is None:
        _db["conn"] = dbconn.connect(timeout=4)
    name = table()
    if name not in _db["ready"]:
        with _db["conn"].cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS %s (id VARCHAR(40) PRIMARY KEY, owner VARCHAR(190), kind VARCHAR(40), "
                        "mkey VARCHAR(400), value JSON, text TEXT, source JSON, created_at VARCHAR(40), sheet_id VARCHAR(60), "
                        "owner_id VARCHAR(190), owner_name VARCHAR(190))" % name)
        _db["ready"].add(name)
    return _db["conn"]


def _in_db(work):
    """Runs `work(connection)`; one reconnect if the kept connection has gone. Records how the database is doing."""
    if db_off():
        _db.update(state="off", error="switched off (SIGNOFF_MEMORY_DB=off)")
        raise ConnectionError(_db["error"])
    with _lock:
        for attempt in (1, 2):
            try:
                out = work(_connect())
                _db.update(state="ok", error=None)
                return out
            except Exception as error:  # noqa: BLE001
                _db.update(conn=None, state="down", error="%s" % type(error).__name__)
                _db["ready"].clear()
                if attempt == 2:
                    raise


def _row_to_db(row):
    return (row["id"], row["owner"], row["kind"], str(row["key"]), json.dumps(row["value"]), row["text"],
            json.dumps(row["source"]), row["created_at"], row.get("sheet_id"), row.get("owner_id"), row.get("owner_name"))


def db_add(rows) -> int:
    """Inserts the rows the table does not have yet. Raises when the database cannot be reached."""
    def work(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM %s" % table())
            have = {r[0] for r in cur.fetchall()}
            new = [r for r in rows if r["id"] not in have]
            if new:
                cur.executemany("INSERT INTO %s (id, owner, kind, mkey, value, text, source, created_at, sheet_id, owner_id, "
                                "owner_name) VALUES (%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s,%%s)" % table(),
                                [_row_to_db(r) for r in new])
                conn.commit()
            return len(new)
    return _in_db(work)


def db_rows() -> list:
    def work(conn):
        with conn.cursor() as cur:
            cur.execute("SELECT id, owner, kind, mkey, value, text, source, created_at, sheet_id, owner_id, owner_name "
                        "FROM %s ORDER BY created_at, id" % table())
            out = []
            for r in cur.fetchall():
                value, source = (json.loads(x) if isinstance(x, (str, bytes)) else x for x in (r[4], r[6]))
                out.append({"id": r[0], "owner": r[1], "kind": r[2], "key": r[3], "value": value, "text": r[5],
                            "source": source, "created_at": r[7], "sheet_id": r[8], "owner_id": r[9], "owner_name": r[10]})
            return out
    return _in_db(work)


def db_status() -> dict:
    return {"state": _db["state"], "error": _db["error"], "table": table()}


# --- the one way in ---------------------------------------------------------------------------------------------

def write(memory: dict, database=True) -> dict:
    """Stores one memory, or raises Refused. The record named by `memory["source"]` must exist and must prove this
    owner, kind, key, value and sentence; a strike or anything else owned by the approver needs the receipt of a
    verified signed request. Returns the stored row."""
    if not isinstance(memory, dict):
        raise Refused("no_source", "a memory must name the record it comes from")
    proved = sources.prove(memory.get("source"))
    row = next((p for p in proved if all(p.get(k) == memory.get(k) for k in ("owner", "kind", "key"))), None)
    if row is None:
        raise Refused("record_says_otherwise", "the record does not prove a %r memory owned by %r about %r" % (
            memory.get("kind"), memory.get("owner"), memory.get("key")))
    differs = [k for k in OWNED if k in memory and memory[k] != row[k]]
    if differs:
        raise Refused("record_says_otherwise", "the record proves something else for: %s" % ", ".join(differs))
    keep([row], database=database)
    return row


def keep(rows, database=True) -> dict:
    """Adds proved rows to the mirror and, unless told not to, to SingleStore. Says where they went."""
    out = {"mirror_added": _mirror_add(rows), "database_added": None, "database": None}
    if database:
        try:
            out["database_added"] = db_add(rows)
            out["database"] = "ok"
        except Exception:  # noqa: BLE001
            out["database"] = "not reached (%s); rows are in the mirror only" % _db["error"]
    return out


def sync(database=False) -> dict:
    """Reads every record again and keeps the memories they prove. `{memories, not_memories, kept}`.
    `database=False` touches only the local mirror (the engine's reset must not wait for a network)."""
    derived = sources.derive()
    return dict(derived, kept=keep(derived["memories"], database=database))


_read = {"key": None, "at": 0.0, "rows": None, "read_from": None}
FRESH_S = 10.0


def read() -> dict:
    """Every stored row, each marked `proved` (a record on disk still proves it). Rows come from SingleStore; if it
    cannot be reached they come from the mirror, and `read_from` says so. The database is asked again when the
    records prove something new, and otherwise at most every ten seconds (`read_at` is the time of the last asking)."""
    derived = sources.derive()
    proved = {m["id"]: m for m in derived["memories"]}
    key = (table(), str(mirror_file()), db_off(), frozenset(proved))
    with _lock:
        if _read["key"] != key or time.time() - _read["at"] > FRESH_S:
            keep(derived["memories"], database=True)
            try:
                rows, read_from = db_rows(), "singlestore"
            except Exception:  # noqa: BLE001
                rows, read_from = mirror_rows(), "mirror (database not reached: %s)" % _db["error"]
            _read.update(key=key, at=time.time(), rows=rows, read_from=read_from)
        rows = [dict(r) for r in _read["rows"]]
        read_from, read_at = _read["read_from"], _read["at"]
    for row in rows:
        mine = proved.get(row.get("id"))
        row["proved"] = bool(mine) and all(mine[k] == row.get(k) for k in OWNED)
    return {"rows": rows, "read_from": read_from, "read_at": datetime.datetime.fromtimestamp(read_at).astimezone().isoformat(timespec="seconds"),
            "database": db_status(), "mirror": {"file": sources._rel(mirror_file()), "rows": len(mirror_rows())},
            "not_memories": derived["not_memories"]}
