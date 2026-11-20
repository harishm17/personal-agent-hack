"""Airbyte sync: the stores' real product records and answers reach the app's database through Airbyte.

  exported files (data/order/*.jsonl)  --HTTPS-->  Airbyte File source  -->  Airbyte MySQL destination
  (a local MySQL staging container, port 3307)  -->  copied by `load_into_singlestore` into SingleStore
  tables airbyte_pool and airbyte_store_answers (database signoff), with the Airbyte job id on every row.

Why the staging hop: Airbyte's MySQL destination loads with LOAD DATA, which SingleStore rejects
("Separators which are not distinct"); Airbyte 2.5.0 lists no SingleStore destination.
Why a public HTTPS address for the files: Airbyte's File source only takes HTTPS; a quick tunnel to
port 8005 (`serve.py`) carries the export, its address is in data/order/export_url.txt.

Run: uv run python -m signoff.airbyte.sync
"""
import json
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor

from signoff import config
from signoff.airbyte import ab, export

ROOT = pathlib.Path(__file__).resolve().parents[2]
URL_FILE = ROOT / "data" / "order" / "export_url.txt"
STAGING = {"host": "host.docker.internal", "port": 3307, "database": "staging", "username": "root",
           "password": "staging"}  # a throwaway local container; not a secret
STREAMS = [
    {"name": "airbyte_pool", "file": "pool.jsonl", "format": "jsonl", "count_key": "pool"},
    {"name": "airbyte_store_answers", "file": "store_answers.jsonl", "format": "jsonl", "count_key": "store_answers"},
]
WAIT_SECONDS = 900


def export_url() -> str:
    url = config.env("AIRBYTE_EXPORT_URL") or (URL_FILE.read_text().strip() if URL_FILE.exists() else "")
    return url.replace("https://", "").rstrip("/")


def _find(kind: str, name: str):
    for item in ab.call("GET", f"/{kind}?limit=100")["data"]:
        if item["name"] == name:
            return item
    return None


def _upsert(kind: str, name: str, create: dict, configuration: dict) -> dict:
    found = _find(kind, name)
    if found:
        idk = kind[:-1] + "Id"
        return ab.call("PATCH", f"/{kind}/{found[idk]}", {"configuration": configuration})
    return ab.call("POST", f"/{kind}", {"name": name, **create, "configuration": configuration})


def ensure() -> list[dict]:
    """Creates or updates source, destination and connection for each stream; returns the connections."""
    ws = ab.call("GET", "/workspaces")["data"][0]["workspaceId"]
    dest = _upsert("destinations", "local MySQL staging", {"workspaceId": ws},
                   {"destinationType": "mysql", "ssl": False, **STAGING})
    out = []
    for s in STREAMS:
        src = _upsert("sources", f"export {s['file']}", {"workspaceId": ws},
                      {"sourceType": "file", "dataset_name": s["name"], "format": s["format"],
                       "url": f"https://{export_url()}/{s['file']}", "provider": {"storage": "HTTPS", "user_agent": False}})
        cname = f"{s['name']} to staging"
        conn = _find("connections", cname)
        if not conn:
            conn = ab.call("POST", "/connections", {
                "name": cname, "sourceId": src["sourceId"], "destinationId": dest["destinationId"],
                "schedule": {"scheduleType": "manual"}, "namespaceDefinition": "destination",
                "configurations": {"streams": [{"name": s["name"], "syncMode": "full_refresh_overwrite"}]}})
        out.append({"stream": s, "connection_id": conn["connectionId"]})
    return out


def _wait(job_id: int) -> dict:
    end = time.time() + WAIT_SECONDS
    while time.time() < end:
        j = ab.call("GET", f"/jobs/{job_id}")
        if j["status"] in ("succeeded", "failed", "cancelled"):
            return j
        time.sleep(3)
    ab.call("DELETE", f"/jobs/{job_id}")
    return {**ab.call("GET", f"/jobs/{job_id}"), "status": "timed_out"}


def _run_one(item: dict) -> dict:
    job = ab.call("POST", "/jobs", {"connectionId": item["connection_id"], "jobType": "sync"})
    j = _wait(job["jobId"])
    return {"stream": item["stream"]["name"], "connection_id": item["connection_id"], "job_id": job["jobId"],
            "status": j["status"], "rows_synced": j.get("rowsSynced"), "duration": j.get("duration"),
            "started_at": j.get("startTime")}


# ---- staging MySQL -> SingleStore -------------------------------------------------------------

def _staging():
    import singlestoredb as s2
    return s2.connect(host="127.0.0.1", port=STAGING["port"], user=STAGING["username"],
                      password=STAGING["password"], database=STAGING["database"], connect_timeout=5)


def _singlestore():
    from signoff.db import conn
    return conn.connect(timeout=10)


DDL = {
    "airbyte_pool": """CREATE ROWSTORE TABLE IF NOT EXISTS airbyte_pool (
        store VARCHAR(80) NOT NULL, product_id VARCHAR(120) NOT NULL, variant_id VARCHAR(120), title VARCHAR(400),
        price_cents INT, url VARCHAR(600), text TEXT, fetched_at VARCHAR(40), product_key VARCHAR(300),
        line_ids JSON, airbyte_job_id BIGINT, airbyte_synced_at DATETIME, PRIMARY KEY (store, product_id))""",
    "airbyte_store_answers": """CREATE ROWSTORE TABLE IF NOT EXISTS airbyte_store_answers (
        store VARCHAR(80) NOT NULL PRIMARY KEY, asked_at VARCHAR(40), question TEXT, answer TEXT,
        delivery_stated TINYINT, delivery_quote TEXT, days_low INT, days_high INT, returnable VARCHAR(20),
        return_fee TEXT, return_quote TEXT, airbyte_job_id BIGINT, airbyte_synced_at DATETIME)""",
    "airbyte_runs": """CREATE ROWSTORE TABLE IF NOT EXISTS airbyte_runs (
        run_id BIGINT AUTO_INCREMENT PRIMARY KEY, finished_at DATETIME, ok TINYINT, detail JSON)""",
}
COLUMNS = {
    "airbyte_pool": ["store", "product_id", "variant_id", "title", "price_cents", "url", "text", "fetched_at",
                     "product_key", "line_ids"],
    "airbyte_store_answers": ["store", "asked_at", "question", "answer", "delivery_stated", "delivery_quote",
                              "days_low", "days_high", "returnable", "return_fee", "return_quote"],
}


def _clean(table: str, row: list) -> list:
    row = list(row)
    if table == "airbyte_pool":
        row[COLUMNS[table].index("line_ids")] = json.dumps([x for x in (row[-1] or "").split(",") if x])
    if table == "airbyte_store_answers":
        for k in ("delivery_stated",):
            i = COLUMNS[table].index(k)
            row[i] = None if row[i] is None else int(bool(row[i]))
    return row


def load_into_singlestore(results: list[dict]) -> dict:
    """Copies what Airbyte delivered to staging into SingleStore; returns row counts per table."""
    s, t = _staging(), _singlestore()
    counts = {}
    try:
        sc, tc = s.cursor(), t.cursor()
        for name in ("airbyte_pool", "airbyte_store_answers", "airbyte_runs"):
            tc.execute(DDL[name])
        for r in results:
            if r["status"] != "succeeded":
                continue
            table, cols = r["stream"], COLUMNS[r["stream"]]
            # The raw records Airbyte delivered (`_airbyte_data`). The typed table the MySQL destination
            # builds from them nulls strings over about 510 characters, so it is not used.
            sc.execute(f"SELECT _airbyte_data FROM airbyte_internal.{STAGING['database']}_raw__stream_{table}")
            records = [json.loads(x[0]) if isinstance(x[0], (str, bytes)) else x[0] for x in sc.fetchall()]
            rows = [_clean(table, [rec.get(c) for c in cols]) for rec in records]
            tc.execute(f"DELETE FROM {table}")
            sql = (f"INSERT INTO {table} ({', '.join(cols)}, airbyte_job_id, airbyte_synced_at) "
                   f"VALUES ({', '.join(['%s'] * len(cols))}, %s, NOW())")
            tc.executemany(sql, [x + [r["job_id"]] for x in rows])
            counts[table] = len(rows)
    finally:
        s.close()
        t.close()
    return counts


def record(detail: dict) -> None:
    try:
        t = _singlestore()
        try:
            cur = t.cursor()
            cur.execute(DDL["airbyte_runs"])
            cur.execute("INSERT INTO airbyte_runs (finished_at, ok, detail) VALUES (NOW(), %s, %s)",
                        (int(detail["ok"]), json.dumps(detail)))
        finally:
            t.close()
    except Exception:  # noqa: BLE001
        pass


def run() -> dict:
    """Exports, runs the syncs through Airbyte, copies to SingleStore, records the run. Never raises."""
    started = time.time()
    detail = {"ok": False, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    try:
        expected = export.write_all()
        items = ensure()
        with ThreadPoolExecutor(len(items)) as pool:
            results = list(pool.map(_run_one, items))
        detail.update(jobs=results, expected=expected)
        loaded = load_into_singlestore(results)
        detail.update(loaded=loaded)
        detail["ok"] = all(r["status"] == "succeeded" for r in results) and all(
            loaded.get(s["name"]) == expected[s["count_key"]] for s in STREAMS)
    except Exception as error:  # noqa: BLE001
        detail["error"] = repr(error)[:400]
    detail["seconds"] = round(time.time() - started, 1)
    record(detail)
    return detail


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
