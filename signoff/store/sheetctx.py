"""Which sheet is active, and where its files are. sheet1 keeps data/pool, data/store_answers; any other sheet keeps its files
under data/<sheet id>/ (pool/, store_answers/). The engine says which sheet is on the table; without it, SIGNOFF_SHEET."""
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"


def active_id() -> str:
    try:
        from signoff.engine import state as engine
        sid = getattr(engine, "_s", {}).get("sheet_id")
        if sid:
            return str(sid)
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get("SIGNOFF_SHEET") or "sheet1"


def sheet(sheet_id: str | None = None) -> dict:
    """The active sheet as the engine holds it now (limits may have moved), else the file on disk."""
    sheet_id = sheet_id or active_id()
    try:
        from signoff.engine import state as engine
        s = getattr(engine, "_s", {}).get("sheet")
        if s and s.get("id") == sheet_id:
            return s
    except Exception:  # noqa: BLE001
        pass
    return json.loads((ROOT / "sheets" / f"{sheet_id}.json").read_text())


def pool_dir(sheet_id: str | None = None) -> pathlib.Path:
    sid = sheet_id or active_id()
    return DATA / "pool" if sid == "sheet1" else DATA / sid / "pool"


def answers_dir(sheet_id: str | None = None) -> pathlib.Path:
    sid = sheet_id or active_id()
    return DATA / "store_answers" if sid == "sheet1" else DATA / sid / "store_answers"


def asked_dir(sheet_id: str | None = None) -> pathlib.Path:
    return answers_dir(sheet_id) / "asked"


def all_pool_dirs() -> list[pathlib.Path]:
    return [DATA / "pool", *sorted(p for p in DATA.glob("sheet*/pool"))]


def all_answer_dirs() -> list[pathlib.Path]:
    return [DATA / "store_answers", *sorted(p for p in DATA.glob("sheet*/store_answers"))]
