"""Pool and store answers from data/, falling back to fixtures/."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def _read_all(folder: pathlib.Path) -> list:
    out: list = []
    for f in sorted(folder.glob("*.json")):
        d = json.loads(f.read_text())
        out.extend(d if isinstance(d, list) else [d])
    return out


def load() -> tuple[list, list]:
    pool = _read_all(ROOT / "data" / "pool")
    answers = _read_all(ROOT / "data" / "store_answers") if (ROOT / "data" / "store_answers").exists() else []
    if not pool:
        pool = json.loads((ROOT / "fixtures" / "pool.json").read_text())
    if not answers:
        answers = json.loads((ROOT / "fixtures" / "store_answers.json").read_text())
    return pool, answers
