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


def test_product_key_is_the_stores_own_fields_or_the_title_and_never_a_brand_list():
    assert build_pool.product_key({"title": "Wonder EZ Adjust Bed Rail by Stander"}) == "wonder ez adjust bed rail by stander"
    assert build_pool.product_key({"title": "Shower Chair", "vendor": "Vive"}) == "vive shower chair"
    assert build_pool.product_key({"title": "Vive Shower Chair", "vendor": "Vive"}) == "vive shower chair"
    assert build_pool.product_key({"title": "T0338W", "vendor": "HOROW", "model": "T0338W-10"}) == "horow t0338w 10"
    assert not hasattr(build_pool, "BRANDS") and not hasattr(build_pool, "RULES")


def test_every_product_carries_the_stores_first_image_or_none():
    import glob
    rows = [r for f in glob.glob(str(ROOT / "data" / "pool" / "*.json")) + glob.glob(str(ROOT / "data" / "sheet2" / "pool" / "*.json"))
            for r in json.loads(open(f).read())]
    assert rows and all("image_url" in r for r in rows)
    assert all(r["image_url"] is None or r["image_url"].startswith("https://") for r in rows)
    assert build_pool.image_url({"media": []}) is None and build_pool.image_url({}) is None
    assert build_pool.image_url({"media": [{"url": "https://x/a.jpg"}, {"url": "https://x/b.jpg"}]}) == "https://x/a.jpg"


def test_every_pool_product_carries_every_in_stock_option():
    import glob
    rows = [r for f in glob.glob(str(ROOT / "data" / "pool" / "*.json")) + glob.glob(str(ROOT / "data" / "sheet2" / "pool" / "*.json"))
            for r in json.loads(open(f).read())]
    for r in rows:
        o = r["options"]
        assert o and all(set(x) == {"variant_id", "title", "price_cents", "available"} and x["available"] for x in o)
        cheapest = min(o, key=lambda x: x["price_cents"])
        assert r["variant_id"] == cheapest["variant_id"] or r["price_cents"] == cheapest["price_cents"]  # the old top-level fields
        assert any(x["variant_id"] == r["variant_id"] for x in o)
    assert any(len(r["options"]) > 1 for r in rows)
    prod = {"variants": [{"id": "a", "title": "12 Inch", "price": {"amount": 5}, "availability": {"available": True}},
                         {"id": "b", "title": "16 Inch", "price": {"amount": 6}, "availability": {"available": False}}]}
    assert build_pool.options_of(prod) == [{"variant_id": "a", "title": "12 Inch", "price_cents": 5, "available": True}]


def test_questions_read_naturally_for_singular_and_plural_needs():
    assert "order a shower chair today" in ask.question_for("shower chair") and "can an opened shower chair be returned" in ask.question_for("shower chair")
    assert "order an electric scooter today" in ask.question_for("electric scooter")
    assert "order headphones today" in ask.question_for("headphones") and "can opened headphones be returned" in ask.question_for("headphones")


def test_returns_and_delivery_are_read_from_the_right_sentences():
    a = ("For a full-priced U.S. order, delivery takes 2\u20137 business days total. Headphones can be returned within 30 days for a refund. "
         "The policy doesn\u2019t specify whether opened headphones qualify.")
    r = ask.parse_reply("x", "Can an opened pair be returned?", a, "t")
    assert r["delivery"]["quote"] == "For a full-priced U.S. order, delivery takes 2\u20137 business days" and r["returns"]["returnable"] == "unclear"
    r = ask.parse_reply("x", "q", "Delivery timing isn\u2019t specified. Items are eligible for a refund within 14 days of the ship date.", "t")
    assert r["delivery"]["stated"] is False  # a refund window is not a delivery time
    r = ask.parse_reply("x", "q", "The store doesn\u2019t accept returns or exchanges, including for opened drinks.", "t")
    assert r["returns"]["returnable"] == "no"
    assert ask.returnable_from("Returns are accepted within 30 days.") == "unclear"  # nothing about an opened item
