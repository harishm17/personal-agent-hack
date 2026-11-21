"""Code's half of reading reviews: nothing is kept that is not quoted from the page, about this product."""
import json

import pytest

from signoff.reviews import reviews

TITLE = "Acme Folding Walker"
PAGE = ("Acme Folding Walker\n\n4.6 out of 5 stars\n\nBased on 212 reviews\n\n"
        "It folds flat and my mother uses it every day. Would buy again.\n")
GOOD = {"about": {"quote": "Acme Folding Walker"}, "rating": {"quote": "4.6 out of 5 stars", "value": 4.6, "out_of": 5},
        "review_count": {"quote": "Based on 212 reviews", "value": 212},
        "sentence": {"quote": "It folds flat and my mother uses it every day. Would buy again."}}


def entry(title, pages, proposals):
    return {"title": title, "query": reviews.query_for(title), "sent": {"query": reviews.query_for(title), "numResults": 4,
            "contents": {"text": {"maxCharacters": 3000}}}, "fetched_at": "2026-11-20T14:00:00-08:00", "service": "exa.ai",
            "key_used": "EXA_API_KEY", "ledger": {"n": 1, "sealed_found_in_payload": []},
            "reply": {"results": pages}, "reader": "test",
            "proposals": {url: {"proposal": p, "asked": reviews.ASKED} for url, p in proposals.items()}}


def candidate(cid, title, price, store="shop.example", picked=False, status="inside"):
    return {"id": cid, "status": status, "picked": picked,
            "product": {"title": title, "store": store, "price_cents": price, "variant_title": None}}


def test_the_query_is_the_title_and_the_word_review():
    assert reviews.query_for("Acme  Folding Walker") == "Acme Folding Walker review"


def test_quotes_are_kept_with_offsets_that_hold_in_the_text():
    kept, dropped = reviews.check(GOOD, PAGE)
    assert not dropped
    for what in ("rating", "review_count", "sentence"):
        assert PAGE[kept[what]["start"]:kept[what]["end"]] == kept[what]["quote"]
    assert (kept["rating"]["value"], kept["rating"]["out_of"], kept["review_count"]["value"]) == (4.6, 5, 212)
    assert kept["sentence"]["quote"] == "It folds flat and my mother uses it every day."  # one sentence at most


def test_a_quote_that_is_not_on_the_page_is_dropped():
    kept, dropped = reviews.check({"rating": {"quote": "4.9 out of 5 stars", "value": 4.9, "out_of": 5}}, PAGE)
    assert kept == {} and dropped[0]["reason"] == "the quote is not in the page's text"


def test_a_number_that_is_not_in_its_quote_is_dropped():
    kept, dropped = reviews.check({"rating": {"quote": "4.6 out of 5 stars", "value": 4.8, "out_of": 5},
                                   "review_count": {"quote": "Based on 212 reviews", "value": 2120}}, PAGE)
    assert kept == {} and {d["what"] for d in dropped} == {"rating", "review_count"}


def test_a_scale_the_page_does_not_write_is_not_supplied():
    text = "Acme Folding Walker\nRated 4.5 from 138 reviews.\nAverage: (5.00)\n"
    kept, _ = reviews.check({"rating": {"quote": "Rated 4.5 from 138 reviews.", "value": 4.5, "out_of": 5}}, text)
    assert kept["rating"]["out_of"] is None
    kept, _ = reviews.check({"rating": {"quote": "(5.00)", "value": 5, "out_of": 5}}, text)
    assert kept["rating"]["out_of"] is None  # one number cannot be both the rating and its scale


def test_a_page_with_zero_reviews_gives_no_rating():
    text = "Acme Folding Walker\n0 / 5 0 reviews\nBe the first to write a review.\n"
    kept, dropped = reviews.check({"rating": {"quote": "0 / 5", "value": 0, "out_of": 5},
                                   "review_count": {"quote": "0 reviews", "value": 0}}, text)
    assert kept == {} and len(dropped) == 2


def test_a_count_must_say_what_it_counts():
    kept, dropped = reviews.check({"review_count": {"quote": "4.6 out of 5", "value": 5}}, PAGE)
    assert kept == {} and "counts reviews" in dropped[0]["reason"]


def test_a_page_whose_title_does_not_name_the_product_is_dropped_with_the_reason():
    ok, reason = reviews.names_product(TITLE, {"title": "The 5 best walkers of the year", "text": PAGE})
    assert not ok and "acme" in reason and "folding" in reason
    assert reviews.names_product(TITLE, {"title": "", "text": "ACME folding walker - review\nmore"})[0]


def test_a_rating_that_belongs_to_another_product_on_the_page_is_dropped(monkeypatch):
    listing = "Best Folding Walker picks, Acme and others\n| Otherco Rollator | 4.8 (786 ratings) |\n"
    page = {"title": "Best Acme Folding Walker alternatives", "url": "https://guide.example/best", "text": listing}
    said = {"about": {"quote": "Otherco Rollator"}, "rating": {"quote": "4.8 (786 ratings)", "value": 4.8, "out_of": 5},
            "review_count": {"quote": "4.8 (786 ratings)", "value": 786}}
    reviews._save(TITLE, entry(TITLE, [page], {page["url"]: said}))
    got = reviews.product_reviews(TITLE)
    assert got["found"] is False and got["note"] == "no reviews found" and got["rating"] is None
    assert "not this product" in got["dropped"][0]["reason"]
    reviews._save(TITLE, entry(TITLE, [page], {page["url"]: dict(said, about=None)}))
    assert reviews.product_reviews(TITLE)["found"] is False


def test_nothing_searched_is_said_plainly_and_replay_fetches_nothing():
    got = reviews.product_reviews("Never Searched Chair")
    assert (got["found"], got["searched"], got["note"], got["sources"]) == (False, False, "not searched yet", [])
    assert reviews.search("Never Searched Chair") is None  # replay mode: no network, no cache written
    assert not reviews.DIR.exists()


def test_best_reviewed_is_offered_with_its_minimum_and_never_applied():
    def page(title, rating, count, site):
        text = "%s\n%s out of 5 stars\nBased on %d reviews\n" % (title, rating, count)
        said = {"about": {"quote": title}, "rating": {"quote": "%s out of 5 stars" % rating, "value": rating, "out_of": 5},
                "review_count": {"quote": "Based on %d reviews" % count, "value": count}}
        url = "https://%s/p" % site
        reviews._save(title, entry(title, [{"title": title, "url": url, "text": text}], {url: said}))
    page("Acme Folding Walker", 4.2, 300, "a.example")
    page("Bolt Folding Walker", 5.0, 3, "b.example")      # higher, but three reviews: below the minimum
    page("Crest Folding Walker", 4.7, 40, "c.example")
    line = {"line_id": "L4", "need": "walker", "candidates": [
        candidate("L4:a", "Acme Folding Walker", 4000, picked=True), candidate("L4:b", "Bolt Folding Walker", 4500),
        candidate("L4:c", "Crest Folding Walker", 6000), candidate("L4:d", "Dune Folding Walker", 3000, status="outside"),
        candidate("L4:e", "Elm Folding Walker", 7000)]}
    before = json.dumps(line, sort_keys=True)
    out = reviews.for_line(line)
    assert json.dumps(line, sort_keys=True) == before  # the line, its statuses and its pick are untouched
    assert [c["candidate_id"] for c in out["candidates"]] == ["L4:a", "L4:b", "L4:c", "L4:e"]  # only those that pass
    best = out["best_reviewed"]
    assert best["candidate_id"] == "L4:c" and best["is_the_current_pick"] is False
    assert best["to_take_it"]["body"] == {"line_id": "L4", "candidate_id": "L4:c"}
    assert out["summary"]["applied"] is False and out["summary"]["minimum_reviews"] == reviews.MINIMUM_REVIEWS
    bolt = out["candidates"][1]
    assert "from 3 reviews" in bolt["note"] and "one site: b.example" in bolt["note"]
    assert out["candidates"][3]["note"] == "not searched yet"


def test_the_log_shows_what_was_sent_and_the_ledger_row():
    reviews._save(TITLE, entry(TITLE, [{"title": TITLE, "url": "https://a.example/p", "text": PAGE}], {"https://a.example/p": GOOD}))
    step = reviews.log()[0]
    assert step["step"] == "Reviews read" and step["sent"]["query"] == "Acme Folding Walker review"
    assert step["sent_is_only_the_product_title_and_review"] is True and step["product_quotes_kept"] == 3


def test_the_sent_body_shown_is_the_one_the_ledger_hashed():
    from signoff import obs
    body = {"query": "Acme Folding Walker review", "numResults": 4, "contents": {"text": {"maxCharacters": 3000}}}
    row = obs.egress("exa.ai", "search the web for reviews of one product", body, ["product"], mask=[TITLE])
    assert reviews._payload_hash(body) == row["payload_sha256"] and row["sealed_found_in_payload"] == []


def test_the_routes_read_only_and_leave_the_engine_state_alone():
    from fastapi.testclient import TestClient
    from signoff.app import app
    from signoff.engine import state as engine
    client = TestClient(app)
    engine.get_state()  # the engine loads on first use; the count starts after that
    before = engine.version()
    everything = client.get("/api/reviews").json()
    assert everything["lines"] and all(l["summary"]["applied"] is False for l in everything["lines"])
    one = everything["lines"][0]["line_id"]
    assert client.get("/api/reviews", params={"line_id": one}).json()["line_id"] == one
    assert client.get("/api/reviews", params={"line_id": "no such line"}).status_code == 404
    assert client.get("/api/reviews/log").json()["step"] == "Reviews read"
    fetched = client.post("/api/reviews/fetch", json={"line_id": one}).json()  # replay mode: nothing leaves
    assert all(s.get("skipped") for s in fetched["searches"])
    assert engine.version() == before


def test_the_backup_key_is_used_only_when_the_first_is_refused_and_is_named(monkeypatch):
    calls = []

    class Reply:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            assert self.status_code == 200

        def json(self):
            return {"results": []}

    def post(url, headers, json, timeout):
        calls.append(headers["x-api-key"])
        return Reply(402 if headers["x-api-key"] == "first" else 200)

    monkeypatch.setenv("EXA_API_KEY", "first")
    monkeypatch.setenv("EXA_API_KEY_BACKUP", "second")
    monkeypatch.setattr(reviews.httpx, "post", post)
    reply, name, refused = reviews._post({"query": "x review"})
    assert name == "EXA_API_KEY_BACKUP" and calls == ["first", "second"] and refused == ["EXA_API_KEY was refused (HTTP 402)"]


@pytest.mark.live
def test_one_search_goes_through_the_ledger_with_only_the_title(monkeypatch):
    from signoff.obs import _egress_module as ledger
    monkeypatch.setenv("SIGNOFF_MODE", "live")
    got = reviews.search("Carex Folding Walker")
    row = ledger.rows("all")[-1]
    assert row["recipient"] == "exa.ai" and row["sealed_found_in_payload"] == []
    assert got["sent"]["query"] == "Carex Folding Walker review" and got["reply"]["results"]


def test_a_rounded_rating_is_replaced_by_the_number_the_page_writes():
    text = "Acme Folding Walker\nSyndicated rating, 4.5915494 out of 5 stars with 71 reviews on acme.example.\n"
    quote = "Syndicated rating, 4.5915494 out of 5 stars with 71 reviews on acme.example."
    kept, _ = reviews.check({"rating": {"quote": quote, "value": 4.6, "out_of": 5}}, text)
    assert (kept["rating"]["value"], kept["rating"]["out_of"], kept["rating"]["value_as_reported"]) == (4.5915494, 5, 4.6)
    kept, dropped = reviews.check({"rating": {"quote": quote, "value": 4.9, "out_of": 5}}, text)
    assert kept == {} and dropped[0]["reason"] == "the reported rating is not in the quoted words"


def test_the_second_quote_is_used_only_when_it_states_the_scale():
    text = "Acme Folding Walker\n4.6(71 reviews)\nRated 4.6 out of 5 stars\n"
    said = {"proposal": {"about": {"quote": "Acme Folding Walker"}, "rating": {"quote": "4.6(71 reviews)", "value": 4.6, "out_of": 5}}}
    assert reviews.lacks_scale(said, {"text": text})
    assert reviews.effective(dict(said, rating_second={"quote": "Rated 4.6 out of 5 stars", "value": 4.6, "out_of": 5}), text)["rating"]["quote"] == "Rated 4.6 out of 5 stars"
    for second in (None, {"quote": "4.6 out of 5, they say", "value": 4.6, "out_of": 5}, {"quote": "4.6(71 reviews)", "value": 4.6, "out_of": 5}):
        assert reviews.effective(dict(said, rating_second=second), text)["rating"]["quote"] == "4.6(71 reviews)"


def test_ratings_reads_the_cache_only_and_states_its_minimum():
    import signoff.reviews as package

    def page(title, quote, value, count, site):
        text = "%s\n%s\nBased on %d reviews\n" % (title, quote, count)
        said = {"about": {"quote": title}, "rating": {"quote": quote, "value": value, "out_of": 5},
                "review_count": {"quote": "Based on %d reviews" % count, "value": count}}
        url = "https://%s/p" % site
        reviews._save(title, entry(title, [{"title": title, "url": url, "text": text}], {url: said}))
    line = {"line_id": "L4", "need": "walker", "candidates": [
        candidate("L4:a", "Acme Folding Walker", 4000, picked=True), candidate("L4:b", "Bolt Folding Walker", 4500),
        candidate("L4:c", "Crest Folding Walker", 6000), candidate("L4:d", "Dune Folding Walker", 3000, status="outside"),
        candidate("L4:e", "Elm Folding Walker", 7000)]}
    assert package.ratings("L4", line) == {}                      # nothing cached: empty, and replay mode proves no network
    page("Acme Folding Walker", "4.2 out of 5 stars", 4.2, 300, "a.example")
    page("Bolt Folding Walker", "5.0 out of 5 stars", 5.0, 4, "b.example")   # below the minimum of reviews
    page("Crest Folding Walker", "Rated 4.9", 4.9, 80, "c.example")          # the page writes no scale
    page("Dune Folding Walker", "4.9 out of 5 stars", 4.9, 900, "d.example")  # does not pass the order
    assert package.ratings("L4", line) == {"L4:a": {"rating": 4.2, "out_of": 5, "review_count": 300,
                                                    "independent": True, "site": "a.example"}}
    assert package.MINIMUM_REVIEWS == reviews.MINIMUM_REVIEWS == 5 and "MINIMUM_REVIEWS (5)" in package.ratings.__doc__
    assert package.ratings("no such line") == {}
    out = reviews.for_line(line)
    assert out["best_reviewed"]["candidate_id"] == "L4:a"
    said = {c["candidate_id"]: c["ordering"] for c in out["candidates"]}
    assert said["L4:a"] == {"used": True, "reason": None}
    assert said["L4:b"]["reason"] == "rating from 4 reviews, under the minimum of 5: not used for ordering"
    assert said["L4:c"] == {"used": False, "reason": "rating without a stated scale: not used for ordering"}
    assert said["L4:e"] == {"used": False, "reason": "not searched yet"}
    assert {cid for cid, o in said.items() if o["used"]} == set(package.ratings("L4", line))  # one story
    assert (out["summary"]["used_for_ordering"], out["summary"]["with_a_rating_not_used_for_ordering"]) == (1, 2)


def test_a_second_quote_with_the_scale_reaches_the_reply():
    text = "Acme Folding Walker\nSyndicated rating, 4.5915494 out of 5 stars with 71 reviews.\n4.6(71 reviews)\n"
    url = "https://a.example/p"
    said = {"about": {"quote": "Acme Folding Walker"}, "rating": {"quote": "4.6(71 reviews)", "value": 4.6, "out_of": 5},
            "review_count": {"quote": "4.6(71 reviews)", "value": 71}}
    saved = entry(TITLE, [{"title": TITLE, "url": url, "text": text}], {url: said})
    reviews._save(TITLE, saved)
    assert reviews.product_reviews(TITLE)["out_of"] is None
    saved["proposals"][url]["rating_second"] = {"quote": "Syndicated rating, 4.5915494 out of 5 stars with 71 reviews.", "value": 4.6, "out_of": 5}
    reviews._save(TITLE, saved)
    got = reviews.product_reviews(TITLE)
    assert (got["rating"], got["out_of"], got["review_count"]) == (4.5915494, 5, 71)


def test_a_rating_on_the_sellers_own_page_is_marked_and_still_ordered_the_same():
    assert reviews.same_seller("parentgiving.com", "parentgiving.com") and reviews.same_seller("reviews.shop.example", "www.shop.example")
    assert reviews.same_seller("shop.example.co.uk", "example.co.uk") and not reviews.same_seller("other.co.uk", "example.co.uk")
    assert not reviews.same_seller("walmart.com", "carex.com") and not reviews.same_seller("", "carex.com")
    title, text = "Crest Folding Walker", "Crest Folding Walker\nRated 4.6 out of 5 stars\nBased on 58 reviews\n"
    said = {"about": {"quote": title}, "rating": {"quote": "Rated 4.6 out of 5 stars", "value": 4.6, "out_of": 5},
            "review_count": {"quote": "Based on 58 reviews", "value": 58}}
    url = "https://www.shop.example/products/crest"
    reviews._save(title, entry(title, [{"title": title, "url": url, "text": text}], {url: said}))
    line = {"line_id": "L4", "need": "walker", "candidates": [candidate("L4:c", title, 6000, store="shop.example")]}
    out = reviews.for_line(line)
    row = out["candidates"][0]
    assert row["independent"] is False and row["rating_from"] == "the seller's own page"
    assert all(s["seller_page"] is True for s in row["sources"])
    assert out["ratings"]["L4:c"] == {"rating": 4.6, "out_of": 5, "review_count": 58, "independent": False, "site": "shop.example"}
    assert out["best_reviewed"]["candidate_id"] == "L4:c" and out["best_reviewed"]["independent"] is False
    line["candidates"][0]["product"]["store"] = "elsewhere.example"   # the same page, sold by another store
    assert reviews.for_line(line)["ratings"]["L4:c"]["independent"] is True


def test_every_query_is_the_title_and_fixed_words_and_the_same_request_has_one_file():
    assert reviews.queries_for("Acme  Folding Walker") == ["Acme Folding Walker review", "Acme Folding Walker reviews rating",
                                                           "Acme Folding Walker customer reviews"]
    paths = {reviews.cache_path(TITLE, q) for q in reviews.queries_for(TITLE)}
    assert len(paths) == 3 and reviews.cache_path(TITLE, reviews.query_for(TITLE)) in paths


def test_several_sources_are_listed_not_averaged_and_another_site_comes_before_the_sellers_page():
    title = "Crest Folding Walker"

    def page(site, rating, count):
        text = "%s\nRated %s out of 5 stars\nBased on %d reviews\n" % (title, rating, count)
        said = {"about": {"quote": title}, "rating": {"quote": "Rated %s out of 5 stars" % rating, "value": rating, "out_of": 5},
                "review_count": {"quote": "Based on %d reviews" % count, "value": count}}
        return {"title": title, "url": "https://%s/p" % site, "text": text}, said
    (own, own_said), (other, other_said), (few, few_said) = page("shop.example", 4.9, 500), page("b.example", 4.1, 40), page("c.example", 5.0, 2)
    first = entry(title, [own, few], {own["url"]: own_said, few["url"]: few_said})
    second = dict(entry(title, [other, own], {other["url"]: other_said}), query=reviews.queries_for(title)[1])
    second["sent"] = dict(second["sent"], query=second["query"])
    reviews._save(title, first)
    reviews._save(title, second)
    got = reviews.product_reviews(title, "shop.example")
    assert (got["rating"], got["review_count"], got["rating_site"], got["independent"]) == (4.1, 40, "b.example", True)
    assert got["sources_disagree"] is True and len(got["ratings_by_source"]) == 3 and len(got["queries"]) == 2
    assert [(r["site"], r["can_be_ordered"], r["independent"]) for r in got["ratings_by_source"]] == [
        ("b.example", True, True), ("shop.example", True, False), ("c.example", False, True)]
    assert "none is averaged" in got["combined_how"] and "none is averaged" in got["note"]


def test_a_page_that_names_what_the_store_does_not_say_is_another_product(monkeypatch):
    title = "Knee Walker"
    own = frozenset(reviews._words("Knee Walker\nSteerable knee walker with a basket, by Acme. Holds 300 lb."))
    page = {"title": "Otherco Folding Knee Walker", "url": "https://m.example/p", "text": "Otherco Folding Knee Walker\n4.6 out of 5 stars\n562 reviews\n"}
    said = {"about": {"quote": "Otherco Folding Knee Walker"}, "rating": {"quote": "4.6 out of 5 stars", "value": 4.6, "out_of": 5},
            "review_count": {"quote": "562 reviews", "value": 562}}
    ok, reason = reviews.rates_product(title, said, page, own)
    assert not ok and "never says: otherco, folding" in reason
    assert reviews.rates_product(title, said, page, own, own_page=True)[0]          # the seller's own page names it its own way
    same = dict(page, text="Acme Steerable Knee Walker\n4.6 out of 5 stars\n562 reviews\n")
    assert reviews.rates_product(title, dict(said, about={"quote": "Acme Steerable Knee Walker"}), same, own) == (True, "Acme Steerable Knee Walker")
    reviews._save(title, entry(title, [page], {page["url"]: said}))
    monkeypatch.setattr(reviews, "store_words", lambda store, product_id: own)
    got = reviews.product_reviews(title, "acme.example", None, "p1")
    assert got["found"] is False and "never says" in got["dropped"][0]["reason"]
    monkeypatch.setattr(reviews, "store_words", lambda store, product_id: None)   # no store page to compare: said plainly
    got = reviews.product_reviews(title, "acme.example", None, "p2")
    assert got["found"] is True and got["sources"][0]["matched_by"].startswith("name only (the store's own page was not available")
