"""Pool and store answers from data/, falling back to fixtures/."""
import json
import pathlib

from signoff.store import sheetctx

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _read_all(folder: pathlib.Path) -> list:
    out: list = []
    for f in sorted(folder.glob("*.json")):
        d = json.loads(f.read_text())
        out.extend(d if isinstance(d, list) else [d])
    return out


def load(sheet_id: str | None = None) -> tuple[list, list]:
    """(pool, store answers) of the active sheet from data/, falling back to fixtures/."""
    pool_dir, ans_dir = sheetctx.pool_dir(sheet_id), sheetctx.answers_dir(sheet_id)
    pool = _read_all(pool_dir) if pool_dir.exists() else []
    answers = _read_all(ans_dir) if ans_dir.exists() else []
    if not pool:
        pool = json.loads((ROOT / "fixtures" / "pool.json").read_text())
    if not answers:
        answers = json.loads((ROOT / "fixtures" / "store_answers.json").read_text())
    return pool, answers
