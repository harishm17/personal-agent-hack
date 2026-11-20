import json
import pathlib

import pytest

from signoff.engine import receipts

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def records(tmp_path, monkeypatch):
    """A receipt folder and a memory folder of this test's own; the database is switched off."""
    monkeypatch.setattr(receipts, "FOLDER", tmp_path / "receipts")
    monkeypatch.setattr(receipts, "_c", {"id": None, "receipts": [], "file": None, "previous": None})
    monkeypatch.setenv("SIGNOFF_RECEIPTS", "file")
    monkeypatch.setenv("SIGNOFF_MEMORY_DIR", str(tmp_path / "memory"))
    monkeypatch.setenv("SIGNOFF_MEMORY_DB", "off")
    return tmp_path


@pytest.fixture
def sheet():
    return json.loads((ROOT / "sheets" / "sheet4.json").read_text())


@pytest.fixture
def product(sheet):
    """A real product of the pool on the sheet's last line."""
    line_id = sheet["lines"][-1]["id"]
    for path in sorted((ROOT / "data" / "pool").glob("*.json")):
        for p in json.loads(path.read_text()):
            if line_id in (p.get("line_ids") or []):
                return {"line_id": line_id, "product_key": p["product_key"], "title": p["title"]}
    raise AssertionError("the pool has no product on %s" % line_id)


def signed_strike(product, reason, key="key0000000000001", kind="strike", seq=1):
    """What the engine and the signing route write for one accepted strike: the change, then the accepted request."""
    action = {"type": kind, "seq": seq, "line_id": product["line_id"], "product_key": product["product_key"], "reason": reason}
    detail = {"line_id": product["line_id"], "product_key": product["product_key"]}
    if kind == "strike":
        detail["reason"] = reason
    change = receipts.append(kind, "issuer", key, action, detail)
    receipts.signed_request(json.dumps(action), key, True)
    return change
