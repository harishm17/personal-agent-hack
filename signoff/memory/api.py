"""MEMORY routes. Both are GET and change nothing on the sheet."""
from fastapi import APIRouter

from signoff.memory import meaning, recalling, store

router = APIRouter()


def _active_sheet() -> dict:
    from signoff.store import sheetctx
    return sheetctx.sheet()


def _shelf(sheet: dict, recalled: dict) -> list:
    """The four owner slots for the sheet on the table: the shopper's, the approver's, each store's, what was signed for."""
    def cards(entries, kind, owner=None):
        return [{"memory_id": e["memory_id"], "owner": owner or e["store"], "kind": kind, "text": e["text"],
                 "source": e["source"], "at": e["source"].get("at"), "age": e.get("age") or recalling.age(e["source"].get("at")),
                 **{k: e[k] for k in ("fact_id", "value", "unit", "line_id", "product_key", "title", "reason", "key",
                                      "total_cents", "carts") if k in e}} for e in entries]
    return [{"slot": "shopper", "owner": "shopper", "name": (sheet.get("shopper") or {}).get("name"),
             "items": cards(recalled["facts"], "home_measurement", "shopper")},
            {"slot": "approver", "owner": "issuer", "name": (sheet.get("issuer") or {}).get("name"),
             "items": cards(recalled["strikes"], "strike", "issuer")},
            {"slot": "stores", "owner": "each store", "name": None, "items": cards(recalled["store_answers"], "store_answer")},
            {"slot": "bought", "owner": "issuer", "name": (sheet.get("issuer") or {}).get("name"),
             "items": cards(recalled["purchases"], "purchase", "issuer")}]


@router.get("/api/memory")
def memory():
    """Everything remembered, grouped by owner, each row with the record that proves it and its age; and `shelf`, the
    four owner slots holding what a new run of the sheet on the table would recall.
    `{read_from, database, mirror, counts, shelf, owners: [{owner, owner_name, rows: [...]}], not_memories}`."""
    held = store.read()
    sheet = _active_sheet()
    meaning_status = meaning.status()  # as it stood before this call starts a pass
    if held["database"]["state"] == "ok":
        meaning.index_in_background(sheet)  # new memories get their vectors; the reply does not wait for it
    recalled = recalling.recall(sheet)
    on_shelf = {e["memory_id"] for part in ("facts", "strikes", "store_answers", "purchases") for e in recalled[part]}
    owners, kinds = {}, {}
    for row in held["rows"]:
        row["age"] = recalling.age(row.get("created_at"))
        row["on_shelf"] = row["proved"] and row["id"] in on_shelf
        group = owners.setdefault(row["owner"], {"owner": row["owner"], "owner_name": row.get("owner_name"), "rows": []})
        group["owner_name"] = group["owner_name"] or row.get("owner_name")
        group["rows"].append(row)
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return {"read_from": held["read_from"], "read_at": held["read_at"], "database": held["database"], "mirror": held["mirror"],
            "counts": {"rows": len(held["rows"]), "proved": sum(1 for r in held["rows"] if r["proved"]),
                       "not_proved": sum(1 for r in held["rows"] if not r["proved"]), "by_kind": kinds,
                       "on_shelf": len(on_shelf), "records_refused": len(held["not_memories"])},
            "sheet_id": sheet.get("id"), "shelf": _shelf(sheet, recalled), "recall_error": recalled.get("error"),
            "meaning": meaning_status, "owners": list(owners.values()), "not_memories": held["not_memories"],
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
