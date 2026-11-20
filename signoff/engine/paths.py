"""Where a sheet's files are. One rule for every sheet, no sheet named in code:

    a sheet that has its own folder data/<sheet id>/ keeps everything there or under data/figures/<sheet id>/;
    a sheet without one uses the top-level folders (data/pool, data/store_answers, data/figures, data/order).

The pool, raw replies and store answers are the STORE stream's; figures and what is read from the order are
the ENGINE stream's. `SIGNOFF_POOL_DIR` points the pool somewhere else for a trial run.
"""
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def of(sheet_id, data=None):
    data = pathlib.Path(data) if data is not None else ROOT / "data"
    own = (data / str(sheet_id)).is_dir()
    base = data / str(sheet_id) if own else data
    figures = data / "figures" / str(sheet_id) if own else data / "figures"
    pool = pathlib.Path(os.environ["SIGNOFF_POOL_DIR"]) if os.environ.get("SIGNOFF_POOL_DIR") and own else base / "pool"
    return {"pool": pool, "raw": pool / "raw", "answers": pool.parent / "store_answers",
            "replies": pool.parent / "store_answers" / "asked", "figures": figures, "runs": figures / "_runs",
            "asked": figures / "_asked", "instructions": figures / "_instructions", "planted": figures / "_planted",
            "order": (figures / "_order" / "derived.json") if own else data / "order" / "derived.json"}
