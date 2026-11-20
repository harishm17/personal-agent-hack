"""Recall by meaning: which memories are about this item.

Each memory's sentence is embedded once with Superlinked SIE and kept in SingleStore beside the memory. For an item,
its need (the sheet's own words) is embedded as the query, and one SQL statement ranks by dot product and filters by
owner, kind and sheet. Only memories a record still proves come back. Every call to the embedding model is written
to the outbound ledger, so what it was given can be counted.

This ranks what is shown beside an item. It decides nothing: picks, limits and strikes never read it.
"""
import importlib
import json
import threading
import time

from signoff import config
from signoff.memory import sources, store

MODEL = "Qwen/Qwen3-Embedding-4B"
RECIPIENT = "sie:" + MODEL
PURPOSE_INDEX = "memory: embed the sentences of memories"
PURPOSE_QUERY = "embed one item's need, to rank memories against it"
_lock = threading.Lock()
_s = {"dim": None, "indexing": False, "error": None, "indexed_at": None, "ready": set()}
_queries = {}


def _vec_table() -> str:
    return store.table() + "_vec"


def embed(texts, is_query=False, timeout_s=20.0) -> list:
    """One batched call. Raises when the model does not answer in time (a cold model can take minutes)."""
    from sie_sdk import SIEClient
    egress = importlib.import_module("signoff.obs.egress")  # the package also has a function of that name
    egress.record(RECIPIENT, PURPOSE_QUERY if is_query else PURPOSE_INDEX, list(texts),
                  fact_classes=["order"] if is_query else ["home_measurement", "person", "product", "store_text"], kind="model")
    client = SIEClient("https://api.superlinked.com", api_key=config.env("SIE_API_KEY"), timeout_s=timeout_s)
    out = client.encode(MODEL, [{"text": t} for t in texts], is_query=is_query, provision_timeout_s=timeout_s)
    return [[float(x) for x in item["dense"]] for item in out]


def _ensure(conn, dim):
    name = _vec_table()
    if name not in _s["ready"]:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS %s (id VARCHAR(40) PRIMARY KEY, model VARCHAR(80), "
                        "embedding VECTOR(%d) NOT NULL)" % (name, int(dim)))
        _s["ready"].add(name)
    _s["dim"] = dim


def _indexed_ids(conn) -> set:
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES LIKE %s", (_vec_table(),))
        if not cur.fetchall():
            return set()
        cur.execute("SELECT id FROM %s WHERE model = %%s" % _vec_table(), (MODEL,))
        return {r[0] for r in cur.fetchall()}


def index(timeout_s=600.0) -> dict:
    """Embeds every proved memory that has no vector yet and stores the vectors. `{indexed, of, added}`."""
    memories = store.sync(database=True)["memories"]
    have = store._in_db(_indexed_ids)
    new = [m for m in memories if m["id"] not in have]
    if new:
        vectors = embed([m["text"] for m in new], timeout_s=timeout_s)

        def work(conn):
            _ensure(conn, len(vectors[0]))
            with conn.cursor() as cur:
                cur.executemany("INSERT IGNORE INTO %s (id, model, embedding) VALUES (%%s, %%s, %%s)" % _vec_table(),
                                [(m["id"], MODEL, json.dumps(v)) for m, v in zip(new, vectors)])
            conn.commit()
        store._in_db(work)
    _s.update(error=None, indexed_at=time.time())
    return {"indexed": len([m for m in memories if m["id"] in have]) + len(new), "of": len(memories), "added": len(new)}


def index_in_background() -> None:
    """Starts one indexing pass unless one is running. A failure is kept in `status()`."""
    with _lock:
        if _s["indexing"]:
            return
        _s["indexing"] = True

    def run():
        try:
            index()
        except Exception as error:  # noqa: BLE001
            _s["error"] = "%s" % type(error).__name__
        finally:
            _s["indexing"] = False
    threading.Thread(target=run, daemon=True, name="memory-index").start()


def status() -> dict:
    return {"model": MODEL, "indexing": _s["indexing"], "error": _s["error"], "table": _vec_table()}


def need_of(sheet: dict, line_id: str):
    """The item's need in the sheet's own words: what it is and what each limit is called."""
    line = next((l for l in sheet.get("lines") or [] if l.get("id") == line_id), None)
    if line is None:
        return None
    return ". ".join([str(line.get("need"))] + [str(l.get("name")) for l in line.get("limits") or [] if l.get("name")])


def search(sheet: dict, line_id: str, recalled: dict, k: int = 5, kinds=None, timeout_s=8.0) -> dict:
    """The `k` memories nearest in meaning to the item's need, of those `recalled` for the sheet (so a measurement
    that was replaced or a strike that was undone is not ranked). Never raises: a model or database that does not
    answer comes back as `error`, with nothing ranked."""
    need = need_of(sheet, line_id)
    out = {"model": MODEL, "query": need, "recalled": 0, "of": 0, "ranked": [], "error": None,
           "filter": "owner and kind, among the memories recalled for this sheet, in the same SQL statement as the ranking"}
    if need is None:
        return dict(out, error="no line %r on this sheet" % (line_id,))
    held = {e["memory_id"]: e for part in ("facts", "strikes", "store_answers", "purchases") for e in recalled.get(part) or []}
    owners = ["shopper", "issuer"] + list(sheet.get("stores") or [])
    kinds = list(kinds or ["home_measurement", "strike", "store_answer", "purchase"])
    if not held:
        return out
    try:
        if need not in _queries:
            _queries[need] = embed([need], is_query=True, timeout_s=timeout_s)[0]
        vector = _queries[need]

        def work(conn):
            with conn.cursor() as cur:
                marks = lambda items: ",".join(["%s"] * len(items))  # noqa: E731
                cur.execute(
                    "SELECT m.id, m.owner, m.kind, m.mkey, v.embedding <*> (%%s :> VECTOR(%d)) AS score "
                    "FROM %s m JOIN %s v ON v.id = m.id AND v.model = %%s "
                    "WHERE m.owner IN (%s) AND m.kind IN (%s) AND m.id IN (%s) "
                    "ORDER BY score DESC" % (len(vector), store.table(), _vec_table(), marks(owners), marks(kinds), marks(held)),
                    [json.dumps(vector), MODEL, *owners, *kinds, *held])
                return cur.fetchall()
        rows = store._in_db(work)
    except Exception as error:  # noqa: BLE001
        return dict(out, error="recall by meaning did not run (%s)" % type(error).__name__)
    ranked = [{"memory_id": i, "score": round(float(score), 4), "owner": owner, "kind": kind, "key": key,
               "text": held[i]["text"], "source": held[i]["source"]} for i, owner, kind, key, score in rows]
    return dict(out, recalled=len(ranked[:k]), of=len(ranked), ranked=ranked[:k],
                not_indexed_yet=len([e for e in held.values() if e["memory_id"] not in {r["memory_id"] for r in ranked}])
                if set(kinds) >= {"home_measurement", "strike", "store_answer", "purchase"} else None)


def context(rows: list) -> dict:
    """From the outbound ledger's rows: what each model call was given, and whether any of it was memory.
    Memory leaves this module in one call only, the embedding of the memories' sentences; every other call is given none."""
    calls = {}
    for row in rows:
        if row.get("kind") != "model":
            continue
        key = (row.get("recipient"), row.get("purpose"))
        c = calls.setdefault(key, {"recipient": key[0], "purpose": key[1], "calls": 0, "bytes": 0, "given": set(),
                                   "calls_with_a_home_measurement": 0})
        c["calls"] += 1
        c["bytes"] += row.get("bytes") or 0
        c["given"] |= set(row.get("fact_classes") or []) - {"none"}
        c["calls_with_a_home_measurement"] += any(str(h).startswith("home_measurement") for h in row.get("sealed_found_in_payload") or [])
    out = []
    for c in calls.values():
        from_memory = c["purpose"] == PURPOSE_INDEX
        out.append(dict(c, given=sorted(c["given"]), bytes_per_call=round(c["bytes"] / c["calls"]),
                        calls_given_memory=c["calls"] if from_memory else 0))
    out.sort(key=lambda c: -c["calls"])
    return {"model_calls": sum(c["calls"] for c in out), "calls_given_memory": sum(c["calls_given_memory"] for c in out),
            "calls_given_no_memory": sum(c["calls"] - c["calls_given_memory"] for c in out), "by_call": out,
            "source": "the outbound ledger (GET /api/egress), rows of kind model"}
