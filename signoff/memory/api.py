"""MEMORY routes. Both are GET and change nothing on the sheet."""
from fastapi import APIRouter

from signoff.memory import meaning, recalling, store

router = APIRouter()


def _active_sheet() -> dict:
    from signoff.store import sheetctx
    return sheetctx.sheet()


@router.get("/api/memory")
def memory():
    """Everything remembered, grouped by owner, each row with the record that proves it.
    `{read_from, database, mirror, counts, owners: [{owner, owner_name, rows: [...]}], not_memories}`."""
    held = store.read()
    if held["database"]["state"] == "ok":
        meaning.index_in_background()  # new memories get their vectors; the reply does not wait for it
    owners = {}
    for row in held["rows"]:
        group = owners.setdefault(row["owner"], {"owner": row["owner"], "owner_name": row.get("owner_name"), "rows": []})
        group["owner_name"] = group["owner_name"] or row.get("owner_name")
        group["rows"].append(row)
    kinds = {}
    for row in held["rows"]:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return {"read_from": held["read_from"], "database": held["database"], "mirror": held["mirror"],
            "counts": {"rows": len(held["rows"]), "proved": sum(1 for r in held["rows"] if r["proved"]),
                       "not_proved": sum(1 for r in held["rows"] if not r["proved"]), "by_kind": kinds,
                       "records_refused": len(held["not_memories"])},
            "meaning": meaning.status(), "owners": list(owners.values()), "not_memories": held["not_memories"],
            "rule": "A memory is made only from a receipt in a chain that recomputes or from a saved store answer. "
                    "A row no record proves is shown as not proved and is never recalled."}


@router.get("/api/memory/recall")
def recall(line_id: str | None = None):
    """What is recalled for the sheet on the table; with `line_id`, what bears on that one item and why."""
    sheet = _active_sheet()
    recalled = recalling.recall(sheet)
    if line_id is None or recalled.get("error"):
        return recalled
    return dict(recalling.for_line(sheet, line_id, recalled), sheet_id=sheet.get("id"), read_from=recalled["read_from"],
                by_meaning=meaning.search(sheet, line_id, recalled))


@router.get("/api/memory/context")
def context():
    """What each model call behind this sheet was given, and that none but the embedding of memories was given memory.
    A sheet that uses another sheet's readings (`data_from`) counts that sheet's calls too."""
    import importlib
    egress = importlib.import_module("signoff.obs.egress")  # the package also has a function of that name
    sheet = _active_sheet()
    sheets = sorted({sheet.get("id"), sheet.get("data_from") or sheet.get("id")})
    rows = [r for r in egress.rows("all") if r.get("sheet", "sheet1") in sheets]
    return dict(meaning.context(rows), sheet_id=sheet.get("id"), sheets_counted=sheets)
