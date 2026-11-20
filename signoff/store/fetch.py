"""Fetch every query of every line of a sheet from every store of the sheet, once; save the raw replies for replay.
One thread per store, each store called about once a second. Works for any sheet."""
import concurrent.futures as cf
import json
import pathlib
import sys
import time

from signoff import config
from signoff.store import replay, sheetctx, ucp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
raw_path = replay.raw_path
SPACING = 0.8


def fetch_raw(sheet_id: str | None = None, force: bool = False) -> dict:
    """{(store, query): "ok n" | "cached" | "ERR ..."}. In replay mode nothing is fetched."""
    sheet_id = sheetctx.data_id(sheet_id)
    sheet = json.loads((ROOT / "sheets" / f"{sheet_id}.json").read_text())
    raw_dir = sheetctx.pool_dir(sheet_id) / "raw"
    queries = [q for line in sheet["lines"] for q in line["queries"]]

    def one_store(store):
        res = {}
        for q in queries:
            if config.mode() == "replay":
                res[(store, q)] = "replay: not fetched"
                continue
            p = raw_path(store, q, raw_dir)
            if p.exists() and not force:
                res[(store, q)] = "cached"
                continue
            try:
                r = ucp.search_catalog(store, q)
            except Exception as e:  # noqa: BLE001
                res[(store, q)] = "ERR " + repr(e)[:120]
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(r, indent=1))
            res[(store, q)] = "ok %d" % len(r.get("products", []))
            time.sleep(SPACING)
        return res

    out: dict = {}
    with cf.ThreadPoolExecutor(max(1, len(sheet["stores"]))) as ex:
        for r in ex.map(one_store, sheet["stores"]):
            out.update(r)
    return out


if __name__ == "__main__":
    for (s, q), st in fetch_raw(*sys.argv[1:2]).items():
        print(s, q, st)
