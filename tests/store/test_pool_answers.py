import json
import pathlib

from signoff.store import ask, build_pool, pool

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
KEYS = {"store", "product_id", "variant_id", "title", "price_cents", "url", "text", "fetched_at", "product_key", "line_ids"}


def test_pool_shape_and_lines():
    products, answers = pool.load()
    assert products and answers
    assert all(KEYS <= set(p) for p in products)
    assert all(isinstance(p["price_cents"], int) and p["text"] for p in products)
    real = [p for p in products if not p["store"].startswith("fixture")]
    if real:
        lines = {l for p in real for l in p["line_ids"]}
        assert lines == {"L1", "L2", "L3", "L4", "L5", "L6"}
        assert all("<" not in p["text"] for p in real)


def test_store_answer_quotes_are_in_the_reply():
    for f in (ROOT / "data" / "store_answers").glob("*.json"):
        for a in json.loads(f.read_text()):
            if a["delivery"]["quote"]:
                assert a["delivery"]["quote"] in a["answer"]
            if a["returns"]["quote"]:
                assert a["returns"]["quote"] in a["answer"]


def test_parse_reply_unclear_and_no():
    r = ask.parse_reply("x", "q", "Standard shipping is 3–5 days. Opened bath seats cannot be returned.", "t")
    assert r["delivery"]["days_low"] == 3 and r["returns"]["returnable"] == "no"
    r = ask.parse_reply("x", "q", "The store does not specify delivery. An opened seat return isn’t specified here.", "t")
    assert not r["delivery"]["stated"] and r["returns"]["returnable"] == "unclear"


def test_product_key_moves_maker_first():
    assert build_pool.product_key("parentgiving.com", "Wonder EZ Adjust Bed Rail by Stander") == "stander wonder ez adjust bed rail"
    assert build_pool.product_key("carex.com", "Carex Shower Chair") == "carex shower chair"
    assert build_pool.product_key("vivehealth.com", "Shower Chair") == "vive shower chair"
