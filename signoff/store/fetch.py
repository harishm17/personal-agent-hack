"""Fetch every query of every line of a sheet from every store, once; save raw replies for replay."""
import json
import pathlib
import re
import sys
import concurrent.futures as cf

from signoff import config
from signoff.store import replay, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
RAW = ROOT / "data" / "pool" / "raw"


raw_path = replay.raw_path


def fetch_raw(sheet_path: str = "sheets/sheet1.json", force: bool = False) -> dict:
    sheet = json.loads((ROOT / sheet_path).read_text())
    jobs = [(s, q) for s in sheet["stores"] for line in sheet["lines"] for q in line["queries"]]

    def one(job):
        if config.mode() == "replay":
            return job, "replay: not fetched"
        store, q = job
        p = raw_path(store, q)
        if p.exists() and not force:
            return job, "cached"
        try:
            r = ucp.search_catalog(store, q)
        except Exception as e:  # noqa: BLE001
            return job, "ERR " + repr(e)[:120]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(r, indent=1))
        return job, "ok %d" % len(r.get("products", []))

    with cf.ThreadPoolExecutor(3) as ex:
        return dict(ex.map(one, jobs))


if __name__ == "__main__":
    for (s, q), st in fetch_raw(*sys.argv[1:]).items():
        print(s, q, st)
