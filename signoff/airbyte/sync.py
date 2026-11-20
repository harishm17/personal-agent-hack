"""Airbyte sync: the stores' product records, their answers and the therapist's order reach SingleStore.

  exported files (data/order/*.jsonl, order.csv)
    --HTTPS, through a short-lived tunnel-->  Airbyte File source  -->  Airbyte MySQL destination
    (a local MySQL staging container, port 3307)  -->  copied by `load_into_singlestore` into SingleStore
    tables airbyte_pool, airbyte_store_answers, airbyte_order_limits (database signoff), job id on every row.
Airbyte does not write to SingleStore itself: its MySQL destination fails against it (LOAD DATA with
"Separators which are not distinct") and 2.5.0 lists no SingleStore destination.

`python -m signoff.airbyte.sync` is the one command: it starts the staging container if needed, the export
server on port 8005 and a tunnel (the File source takes only HTTPS), runs the three jobs, copies, records the
run (including the tunnel's address) in airbyte_runs, then stops the server and the tunnel.
"""
import contextlib
import json
import pathlib
import re
import subprocess
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from signoff import config
from signoff.airbyte import ab, export, serve

ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTAINER = "airbyte-staging"
STAGING = {"host": "host.docker.internal", "port": 3307, "database": "staging", "username": "root",
           "password": "staging"}  # a throwaway local container; not a secret
STREAMS = [
    {"name": "airbyte_pool", "file": "pool.jsonl", "format": "jsonl", "count_key": "pool"},
    {"name": "airbyte_store_answers", "file": "store_answers.jsonl", "format": "jsonl", "count_key": "store_answers"},
    {"name": "airbyte_order_limits", "file": "order.csv", "format": "csv", "count_key": "order"},
]
WAIT_SECONDS = 900


def _docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout)


def ensure_staging() -> None:
    """Starts the local MySQL staging container if it is not running, and waits until it answers."""
    if not _docker("ps", "-q", "--filter", f"name=^{CONTAINER}$").stdout.strip():
        if _docker("ps", "-aq", "--filter", f"name=^{CONTAINER}$").stdout.strip():
            _docker("start", CONTAINER)
        else:
            _docker("run", "-d", "--name", CONTAINER, "-e", f"MYSQL_ROOT_PASSWORD={STAGING['password']}",
                    "-e", f"MYSQL_DATABASE={STAGING['database']}", "-p", f"{STAGING['port']}:3306", "mysql:8.0",
                    "--default-authentication-plugin=mysql_native_password", timeout=600)
    for _ in range(40):
        try:
            _staging().close()
            return
        except Exception:  # noqa: BLE001
            time.sleep(3)
    raise RuntimeError("the staging MySQL container did not answer")


@contextlib.contextmanager
def short_lived_tunnel():
    """Export server on port 8005 plus a quick tunnel to it; yields the host name; both stop on exit."""
    server = serve.start()
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)
    proc = subprocess.Popen(["cloudflared", "tunnel", "--no-autoupdate", "--url", f"http://127.0.0.1:{serve.PORT}"],
                            stdout=log, stderr=log)
    try:
        host = None
        for _ in range(60):
            time.sleep(1)
            m = re.search(r"https://([a-z0-9-]+\.trycloudflare\.com)", pathlib.Path(log.name).read_text())
            if m:
                host = m.group(1)
                break
            if proc.poll() is not None:
                break
        if not host:
            raise RuntimeError("the tunnel did not start")
        for _ in range(60):  # the name needs a moment before it answers
            try:
                if urllib.request.urlopen(f"https://{host}/pool.jsonl", timeout=5).status == 200:
                    break
            except Exception:  # noqa: BLE001
                time.sleep(2)
        yield host
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        server.shutdown()
        server.server_close()
        pathlib.Path(log.name).unlink(missing_ok=True)


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


def ensure(host: str) -> list[dict]:
    """Creates or updates source, destination and connection for each stream; returns the connections."""
    ws = ab.call("GET", "/workspaces")["data"][0]["workspaceId"]
    dest = _upsert("destinations", "local MySQL staging", {"workspaceId": ws},
                   {"destinationType": "mysql", "ssl": False, **STAGING})
    out = []
    for s in STREAMS:
        src = _upsert("sources", f"export {s['file']}", {"workspaceId": ws},
                      {"sourceType": "file", "dataset_name": s["name"], "format": s["format"],
                       "url": f"https://{host}/{s['file']}", "provider": {"storage": "HTTPS", "user_agent": False}})
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
    "airbyte_order_limits": """CREATE ROWSTORE TABLE IF NOT EXISTS airbyte_order_limits (
        limit_id VARCHAR(40) NOT NULL PRIMARY KEY, line_id VARCHAR(20), need VARCHAR(80), name VARCHAR(80),
        op VARCHAR(2), value DOUBLE, unit VARCHAR(10), bound_source VARCHAR(20), bound_fact VARCHAR(60),
        issuer VARCHAR(120), issued_at VARCHAR(40), order_note TEXT, airbyte_job_id BIGINT,
        airbyte_synced_at DATETIME)""",
    "airbyte_runs": """CREATE ROWSTORE TABLE IF NOT EXISTS airbyte_runs (
        run_id BIGINT AUTO_INCREMENT PRIMARY KEY, finished_at DATETIME, ok TINYINT, detail JSON)""",
}
COLUMNS = {
    "airbyte_order_limits": ["limit_id", "line_id", "need", "name", "op", "value", "unit", "bound_source",
                             "bound_fact", "issuer", "issued_at", "order_note"],
    "airbyte_pool": ["store", "product_id", "variant_id", "title", "price_cents", "url", "text", "fetched_at",
                     "product_key", "line_ids"],
    "airbyte_store_answers": ["store", "asked_at", "question", "answer", "delivery_stated", "delivery_quote",
                              "days_low", "days_high", "returnable", "return_fee", "return_quote"],
}


def _clean(table: str, row: list) -> list:
    row = list(row)
    if table == "airbyte_pool":
        row[COLUMNS[table].index("line_ids")] = json.dumps([x for x in (row[-1] or "").split(",") if x])
    if table == "airbyte_order_limits":
        i = COLUMNS[table].index("value")
        row[i] = None if row[i] in (None, "") or row[i] != row[i] else float(row[i])
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
        for name in (*COLUMNS, "airbyte_runs"):
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
    """Brings up what a sync needs, runs the jobs, copies to SingleStore, records the run, tears down.
    Never raises."""
    started = time.time()
    detail = {"ok": False, "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
              "source": "File (HTTPS)", "destination": "MySQL (local staging)",
              "copy": "copied to SingleStore by signoff.airbyte.sync"}
    try:
        ensure_staging()
        expected = export.write_all()
        with short_lived_tunnel() as host:
            detail["tunnel"] = f"https://{host} (open for this run only)"
            items = ensure(host)
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
