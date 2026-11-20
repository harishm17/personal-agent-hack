import glob
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
KEYS = {"store", "product_id", "variant_id", "title", "price_cents", "url", "text", "fetched_at", "product_key", "line_ids"}


def test_sheet2_pool_has_pool_shape():
    rows = [r for f in glob.glob(str(ROOT / "data" / "sheet2" / "pool" / "*.json")) for r in json.load(open(f))]
    assert len(rows) > 100
    assert all(KEYS <= set(r) and r["text"] and "<" not in r["text"] for r in rows)
    assert len({(r["store"], r["product_id"]) for r in rows}) == len(rows)
