"""Where a sheet's files are. One rule for every sheet, no sheet named in code:

    the first sheet in sheets/ (by file name) is the one whose files sit in the top-level folders
    (data/pool, data/store_answers, data/figures, data/order); every other sheet keeps its pool and store
    answers under data/<sheet id>/ and everything read from them under data/figures/<sheet id>/.

It does not depend on which folders happen to exist: a sheet whose pool has not been fetched has no pool,
it never borrows another sheet's. The pool, raw replies and store answers are the STORE stream's; figures and
what is read from the order are the ENGINE stream's. `SIGNOFF_POOL_DIR` points a sheet's pool elsewhere for a trial.
"""
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def data_sheet(sheet_id):
    """The sheet whose data folder a sheet uses: itself, unless its file says `"data_from": "<another sheet>"`.
    Such a sheet fetches and reads nothing of its own; its order document and what is read from it stay its own."""
    try:
        return json.loads((ROOT / "sheets" / (str(sheet_id) + ".json")).read_text()).get("data_from") or sheet_id
    except (OSError, ValueError):
        return sheet_id


def of(sheet_id, data=None):
    data = pathlib.Path(data) if data is not None else ROOT / "data"
    first = min((p.stem for p in (ROOT / "sheets").glob("*.json")), default=str(sheet_id))
    order_home = data / "figures" / str(sheet_id) / "_order" / "derived.json" if str(sheet_id) != first else \
        data / "order" / "derived.json"
    sheet_id = data_sheet(sheet_id)  # a sheet may use another sheet's fetched pages and readings ("data_from")
    own = str(sheet_id) != first
    base = data / str(sheet_id) if own else data
    figures = data / "figures" / str(sheet_id) if own else data / "figures"
    pool = pathlib.Path(os.environ["SIGNOFF_POOL_DIR"]) if os.environ.get("SIGNOFF_POOL_DIR") and own else base / "pool"
    return {"pool": pool, "raw": pool / "raw", "answers": pool.parent / "store_answers",
            "replies": pool.parent / "store_answers" / "asked", "figures": figures, "runs": figures / "_runs",
            "asked": figures / "_asked", "instructions": figures / "_instructions", "planted": figures / "_planted",
            "order": order_home}  # what was read from the sheet's own order document is always the sheet's own
