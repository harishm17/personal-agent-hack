import json

from signoff.store import build_pool, relevance


def prod(title, collections=(), tags=()):
    return {"id": "p", "title": title, "collections": [{"title": c} for c in collections], "tags": list(tags),
            "variants": [{"id": "v", "title": "Default Title", "price": {"amount": 100}, "availability": {"available": True}}]}


def test_the_head_of_a_phrase_decides_what_the_thing_is():
    assert relevance.belongs(prod("Sublime One Piece Toilet 1.28 gpf", ["Toilets"]), "toilet")[0]
    assert relevance.belongs(prod("Toilet Paper Holder", ["Toilet Accessories"]), "toilet")[0] is False
    assert relevance.belongs(prod("Gel Toilet Seat Cushion"), "toilet")[0] is False
    assert relevance.belongs(prod("Raised Toilet Seat", ["Raised Toilet Seats & Safety Rails"]), "raised toilet seat")[0]
    assert relevance.belongs(prod("Carex Economy Raised Toilet Seat  5-1/2\""), "raised toilet seat")[0]  # a trailing size is not the head


def test_the_rest_of_the_need_must_be_named_somewhere_by_the_store():
    ok, why = relevance.belongs(prod("Wall Grab Bar", ["Bathroom Safety"]), "grab bar")
    assert ok and "grab" in why
    ok, why = relevance.belongs(prod("Bed Assist Bar"), "grab bar")
    assert not ok and "grab" in why
    assert relevance.belongs(prod("Chrome Faucet", ["Bathroom Faucets"]), "bathroom sink faucet")[0]


def test_the_store_gives_its_own_labels_not_a_word_list_of_ours():
    consts = [n for n, v in vars(relevance).items() if n.isupper() and isinstance(v, (list, tuple, set, frozenset, dict))]
    assert consts == []  # no word list in the rule
    assert relevance.stem("Vanities") == "vanity" and relevance.stem("Toilets") == "toilet" and relevance.stem("glass") == "glass"
    assert relevance.store_labels({"collections": [{"title": "A"}], "tags": ["b"], "categories": [{"value": "gid://shopify/x"},
                                                                                                {"value": "Home > Bath"}]}) == ["A", "b", "Home > Bath"]


def test_options_are_every_in_stock_option(tmp_path):
    p = prod("Grab Bar")
    p["variants"] = [{"id": "a", "title": '12"', "price": {"amount": 5}, "availability": {"available": True}},
                     {"id": "b", "title": '16"', "price": {"amount": 7}, "availability": {"available": True}},
                     {"id": "c", "title": '24"', "price": {"amount": 9}, "availability": {"available": False}}]
    assert [o["variant_id"] for o in build_pool.options_of(p)] == ["a", "b"]


def test_the_pool_summary_counts_what_was_dropped_and_why():
    import pathlib
    root = pathlib.Path(__file__).resolve().parent.parent.parent
    for f in (root / "data" / "pool_summary.json", root / "data" / "sheet2" / "pool_summary.json"):
        s = json.loads(f.read_text())
        for store, lines in s["stores"].items():
            for lid, d in lines.items():
                assert d["candidates"] >= d["kept"] and d["dropped"] == len(d["dropped_why"])
                assert all(x["why"] for x in d["dropped_why"])


def test_a_count_is_not_the_head_of_a_phrase():
    assert relevance.belongs(prod("Crayola Crayons 24pk"), "crayons 24")[0]
    assert relevance.belongs(prod("Yoobi Color Block No.2 Pencils 48pk"), "#2 pencils")[0]
    assert relevance.belongs(prod("Mini Binder, 4 Pack"), "pencils")[0] is False
