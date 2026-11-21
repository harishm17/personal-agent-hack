"""What the web says about the products that pass, kept only as exact quotes with their source.

A review is someone else's claim on someone else's site: weaker than a store's own figure, and held to the
same rule. For each passing product one web search is made (the product's title and the word "review",
nothing else). A reader model proposes, per returned page, a rating, a count of reviews and one sentence;
code decides: the page's title must name the product, every quote must sit in the page's text at its
offsets, and every number must be written in its quote. What fails is dropped with the reason. Nothing here
writes engine state or changes a pick.
"""
import concurrent.futures
import datetime
import hashlib
import json
import pathlib
import re
import threading
import time
import urllib.parse

import httpx

from signoff import config, obs
from signoff.engine import rules
from signoff.extract import spans

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DIR = ROOT / "data" / "reviews"
EXA_URL = "https://api.exa.ai/search"
RECIPIENT = "exa.ai"
KEYS = ("EXA_API_KEY", "EXA_API_KEY_BACKUP")  # the second only when the first is refused for key or quota
KEY_OR_QUOTA = (401, 402, 403, 429)
RESULTS = 10
MAX_CHARS = 10000  # a rating is often far down the page
# every query is the product's own title and fixed words about reviews: no limit, no measurement, no person
QUERY_FORMS = ("%s review", "%s reviews rating", "%s customer reviews")
COMBINE = ("several sources are kept for a product and none is averaged. One is shown as the product's rating: a source "
           "that can be ordered (out of five, at least %d reviews) first; among those, another site before the seller's "
           "own page; then the one with the most reviews. Every source is listed in ratings_by_source with its own quote.")
from signoff.reviews import MINIMUM_REVIEWS  # noqa: E402  (stated once, in the package)
SPACING_SECONDS = 0.25
SENTENCE_MOST = 300
READER = "sie:Qwen/Qwen3.8-27B-FP8"
TIE_BREAK = "highest quoted rating out of five; then more reviews; then lower price; then candidate id"
NAME_RULE = ("a page counts only if its title holds every word of the product's title (words of three letters "
             "or more, and numbers), and only if the name the page itself gives to the product it rates, quoted "
             "from the page, holds every one of those words too")
LIMIT = ("a page on another site is matched by name only: a product whose title names no maker can match another "
         "maker's product of the same name, so every source shows the name the page gives it (rated_as)")
_lock = threading.Lock()
_ilock = threading.RLock()
_index = {"sig": None, "dir": None, "by_title": {}, "memo": {}}
_last_call = [0.0]

SYSTEM = """You read one web page about a product and propose quotes. Reply with one JSON object and nothing else:
{"about": {"quote": "..."} or null,
 "rating": {"quote": "...", "value": 4.6, "out_of": 5} or null,
 "review_count": {"quote": "...", "value": 212} or null,
 "sentence": {"quote": "..."} or null}
- about: the full name, as the page writes it, of the one product that the rating, count and sentence you give belong to.
  On a page that lists several products it is the name written beside that rating, not the page's heading.
- rating: the average rating the page gives this product. The quote must contain both the rating and its scale.
- review_count: how many reviews or ratings that average is based on. The quote must contain the number and the word it counts.
- sentence: one sentence written by a reviewer (a customer or a named reviewer) about this product. Not the seller's description.
Every quote is copied character for character from the page text. If the page does not state a thing, give null. Never guess."""


ASKED = hashlib.sha256(SYSTEM.encode()).hexdigest()[:8]  # a proposal made under other instructions is asked again


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def queries_for(title):
    """Every search made for a product: its title and fixed words about reviews, nothing else."""
    name = " ".join(str(title).split())
    return [form % name for form in QUERY_FORMS]


def query_for(title):
    return queries_for(title)[0]


def body_for(query):
    return {"query": query, "numResults": RESULTS, "contents": {"text": {"maxCharacters": MAX_CHARS}}}


def cache_path(title, query=None, body=None):
    """One file per product and request: the same request is never sent twice."""
    query = query or query_for(title)
    body = body or body_for(query)
    slug = re.sub(r"[^a-z0-9]+", "-", str(title).lower()).strip("-")[:60]
    return DIR / ("%s-%s.json" % (slug, _payload_hash(body)[:10]))


def entries(title=None):
    """Every cached search, by product title, oldest first. Read again only when a file in the folder changed."""
    with _ilock:
        files = sorted(DIR.glob("*.json")) if DIR.exists() else []
        sig = tuple((f.name, f.stat().st_mtime_ns) for f in files)
        if sig != _index["sig"] or _index["dir"] != DIR:
            by = {}
            for f in files:
                entry = json.loads(f.read_text())
                entry["file"] = f.name
                by.setdefault(entry["title"], []).append(entry)
            for found in by.values():
                found.sort(key=lambda e: e["fetched_at"])
            _index.update(sig=sig, dir=DIR, by_title=by, memo={})
        return _index["by_title"] if title is None else list(_index["by_title"].get(title, []))


def cached(title):
    found = entries(title)
    return found[0] if found else None


def _save(title, entry):
    DIR.mkdir(parents=True, exist_ok=True)
    if not entry.get("file"):
        entry["file"] = cache_path(title, entry.get("query"), entry.get("sent")).name
    path = DIR / entry["file"]
    part = path.with_suffix(".part")  # written whole, then moved into place: a reader never sees half a file
    part.write_text(json.dumps(entry, ensure_ascii=False, indent=1) + "\n")
    part.replace(path)


def _post(body):
    """The search reply and the name of the key that answered. The backup key is tried only when the first
    is refused for a key or quota reason, and the reply says which one answered."""
    refused = []
    for name in KEYS:
        key = config.env(name)
        if not key:
            refused.append("%s is not set" % name)
            continue
        response = httpx.post(EXA_URL, headers={"x-api-key": key}, json=body, timeout=30.0)
        if response.status_code in KEY_OR_QUOTA:
            refused.append("%s was refused (HTTP %s)" % (name, response.status_code))
            continue
        response.raise_for_status()
        return response.json(), name, refused
    raise RuntimeError("the search service answered no key: " + "; ".join(refused))


def search(title, query=None):
    """The cached entry for one search of a product, fetching it once when it is not there. In replay mode
    nothing is fetched: an uncached search returns None. Calls start at least SPACING_SECONDS apart."""
    query = query or query_for(title)
    body = body_for(query)
    path = cache_path(title, query, body)
    if path.exists():
        return dict(json.loads(path.read_text()), file=path.name, from_cache=True)
    if config.mode() != "live":
        return None
    # the ledger looks in the payload for the sheet's sealed values; the title is the store's own words
    row = obs.egress(RECIPIENT, "search the web for reviews of one product", body, ["product"], mask=[str(title)])
    with _lock:
        wait = SPACING_SECONDS - (time.monotonic() - _last_call[0])
        if wait > 0:
            time.sleep(wait)
        _last_call[0] = time.monotonic()
    reply, key_name, refused = _post(body)
    entry = {"title": title, "query": query, "sent": body, "fetched_at": _now(), "service": RECIPIENT,
             "key_used": key_name, "keys_refused": refused, "file": path.name,
             "ledger": {k: row.get(k) for k in ("n", "at", "recipient", "kind", "purpose", "bytes", "payload_sha256",
                                                "fact_classes", "sealed_found_in_payload")},
             "reply": reply, "proposals": {}, "reader": READER}
    _save(title, entry)
    return entry


# --- code decides -------------------------------------------------------------------------------------------

def _words(text):
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def page_title(result):
    """(title, where it came from): the title the service returned, else the first line of the page's text."""
    title = (result.get("title") or "").strip()
    if title:
        return title, "the page's title"
    for line in (result.get("text") or "").splitlines():
        if line.strip():
            return line.strip()[:200], "the first line of the page's text (the service returned no title)"
    return "", "no title"


def _lacks(title, name):
    """The words of the product's title that `name` does not hold."""
    have = set(_words(name))
    return [w for w in dict.fromkeys(_words(title)) if (len(w) >= 3 or w.isdigit()) and w not in have]


def names_product(title, result):
    """(True, None) when the page's title names the product, else (False, the reason)."""
    shown, _ = page_title(result)
    missing = _lacks(title, shown)
    if missing:
        return False, "the page's title does not name the product (%r lacks: %s)" % (shown[:120], ", ".join(missing))
    return True, None


def rates_product(title, proposal, result):
    """(True, the name as the page writes it) when the product the page rates, by the name quoted from the page,
    is this product; else (False, the reason). A page that lists several products rates each under its own name."""
    about = (proposal or {}).get("about") if isinstance(proposal, dict) else None
    quote = about.get("quote") if isinstance(about, dict) else None
    if not isinstance(quote, str) or not quote.strip():
        return False, "the reader did not quote the name of the product the page rates"
    span = _span(quote, result.get("text") or "") or _span(quote, page_title(result)[0])
    if span is None:
        return False, "the name given for the rated product is not on the page"
    missing = _lacks(title, span["quote"])
    if missing:
        return False, "what the page rates is named %r, not this product (lacks: %s)" % (span["quote"][:120], ", ".join(missing))
    return True, span["quote"]


def site_of(url):
    host = urllib.parse.urlparse(url or "").netloc.lower()
    return host[4:] if host.startswith("www.") else host


def registered_domain(host):
    """The name a site is registered under, from the host alone: its last two labels, or its last three when the
    host ends in a two-letter country code under a short second-level label (example.co.uk). No list of sites."""
    labels = [l for l in str(host or "").lower().strip(".").split(".") if l]
    if len(labels) >= 3 and len(labels[-1]) == 2 and len(labels[-2]) <= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def same_seller(site, store):
    """The review page is on the site of the store that sells the product: the two registered domains are the same."""
    return bool(site) and bool(store) and registered_domain(site) == registered_domain(site_of("//" + str(store)) or store)


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _span(quote, text):
    """The quote as the page writes it, with its offsets, or None. The page's characters replace the proposal's."""
    found = spans.locate(quote if isinstance(quote, str) else "", text)
    if not found:
        return None
    start, end, how = found
    span = {"quote": text[start:end], "start": start, "end": end, "span_match": how}
    span["span_found_in_text"] = rules.span_found(span, text)
    return span if span["span_found_in_text"] else None


def _written(value, numbers):
    """The number in the quote that the reported value stands for: the same number, or one the reader rounded
    (4.5915494 reported as 4.6). The page's number is returned, never the reader's; None when there is none."""
    exact = next((n for n in numbers if abs(value - n) < 1e-6), None)
    if exact is not None:
        return exact
    places = len(repr(float(value)).split(".")[1].rstrip("0"))
    return next((n for n in numbers if abs(round(n, places) - value) < 1e-6), None)


def _first_sentence(span, text):
    """One sentence at most: the span is cut at its first sentence end and at the length limit (still an exact quote)."""
    quote = span["quote"]
    stop = re.search(r"[.!?][\"')\]]*(?=\s)", quote)
    cut = stop.end() if stop else len(quote)
    if cut > SENTENCE_MOST:
        cut = quote.rfind(" ", 0, SENTENCE_MOST)
        cut = cut if cut > 0 else SENTENCE_MOST
    lead = len(quote[:cut]) - len(quote[:cut].lstrip())
    start, end = span["start"] + lead, span["start"] + len(quote[:cut].rstrip())
    return dict(span, quote=text[start:end], start=start, end=end)


def check(proposal, text):
    """(kept, dropped) for one page. kept: {"rating": {...}, "review_count": {...}, "sentence": {...}} with only
    what is quoted exactly; dropped: [{"what", "reason"}]."""
    kept, dropped = {}, []
    proposal = proposal if isinstance(proposal, dict) else {}

    def drop(what, reason):
        dropped.append({"what": what, "reason": reason, "proposed": proposal.get(what)})

    count = proposal.get("review_count")
    if isinstance(count, dict):
        span, value = _span(count.get("quote"), text), count.get("value")
        if span is None:
            drop("review_count", "the quote is not in the page's text")
        elif not _number(value) or value < 0 or float(value) != int(value):
            drop("review_count", "no whole number was reported")
        elif not any(abs(value - n) < 1e-6 for n in spans.numbers_in(span["quote"])):
            drop("review_count", "the reported number is not in the quoted words")
        elif not re.search(r"review|rating|rated", span["quote"], re.I):
            drop("review_count", "the quoted words do not say the number counts reviews or ratings")
        elif value == 0:
            drop("review_count", "the page states 0 reviews")
        else:
            kept["review_count"] = dict(span, value=int(value))

    rating = proposal.get("rating")
    if isinstance(rating, dict):
        span, value, out_of = _span(rating.get("quote"), text), rating.get("value"), rating.get("out_of")
        numbers = spans.numbers_in(span["quote"]) if span else []
        if span is None:
            drop("rating", "the quote is not in the page's text")
        elif not _number(value):
            drop("rating", "no rating was reported")
        elif _written(value, numbers) is None:
            drop("rating", "the reported rating is not in the quoted words")
        elif any(d["reason"] == "the page states 0 reviews" for d in dropped):
            drop("rating", "the page states 0 reviews")
        else:
            # the page's own number is the rating (the reader may have rounded it); the scale counts only if
            # it is written in the quote as a number of its own, beside the rating
            reported, value = value, _written(value, numbers)
            if abs(reported - value) > 1e-6:
                span["value_as_reported"] = reported
            numbers.remove(value)
            stated = _number(out_of) and any(abs(out_of - n) < 1e-6 for n in numbers)
            if value <= 0 or (stated and value > out_of):
                drop("rating", "%g%s is not a rating" % (value, (" out of %g" % out_of) if stated else ""))
            else:
                kept["rating"] = dict(span, value=value, out_of=out_of if stated else None)

    sentence = proposal.get("sentence")
    if isinstance(sentence, dict):
        span = _span(sentence.get("quote"), text)
        if span is None:
            drop("sentence", "the quote is not in the page's text")
        else:
            span = _first_sentence(span, text)
            if len(span["quote"].split()) < 4:
                drop("sentence", "too short to be a sentence")
            else:
                kept["sentence"] = dict(span, said_by="proposed by the reader as a reviewer's words; code checked only "
                                                      "that the page's text holds them")
    return kept, dropped


# --- the reader proposes ------------------------------------------------------------------------------------

def _parse(reply):
    start, end = (reply or "").find("{"), (reply or "").rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reader's reply")
    return json.loads(reply[start:end + 1])


def propose(title, result):
    """The reader's proposal for one page: it is sent the product's title and the page's text, nothing of the sheet."""
    from signoff.extract import reader
    user = "Product: %s\n\nPage title: %s\n\nPage text, between the markers:\n<<<TEXT\n%s\nTEXT>>>" % (
        title, page_title(result)[0], result.get("text") or "")
    reply, _usage, name = reader.ask(READER, SYSTEM, user, purpose="propose review quotes from one web page",
                                     fact_classes=("product",))
    said = {"proposal": _parse(reply), "reader": name, "at": _now(), "asked": ASKED}
    return quote_again(title, result, said)


AGAIN = """Code checked the rating you quoted from this page, %r, and it does not contain the scale the rating is out of.
If the page text writes this same product's average rating together with its scale in one place, reply with one JSON
object {"rating": {"quote": "...", "value": 4.6, "out_of": 5}} whose quote is copied character for character from
that place. If the page writes no scale for the rating, reply {"rating": null}. Never guess a scale."""


def effective(said, text):
    """The proposal code judges: the reader's first, with its second rating quote in place of the first when
    code finds the second on the page with the rating and its scale both written in it."""
    proposal = dict(said.get("proposal")) if isinstance(said.get("proposal"), dict) else {}
    second = said.get("rating_second")
    if isinstance(second, dict):
        kept, _ = check({"rating": second}, text)
        if "rating" in kept and kept["rating"]["out_of"] is not None:
            proposal["rating"] = second
    return proposal


def lacks_scale(said, result):
    """The reader quoted a rating and code found it on the page, but the quoted words state no scale."""
    kept, _ = check(effective(said, result.get("text") or ""), result.get("text") or "")
    return "rating" in kept and kept["rating"]["out_of"] is None


def quote_again(title, result, said):
    """The verification loop, once per page: when the quoted rating states no scale, code says so and the reader
    may quote the place where the page writes both. The second quote is kept beside the first and used only if
    code finds it on the page with the rating and its scale in it (`effective`). Nothing is supplied by code."""
    from signoff.extract import reader
    if said.get("asked_again") or not lacks_scale(said, result):
        return said
    first = said["proposal"]["rating"]
    user = "Product: %s\n\nPage title: %s\n\nPage text, between the markers:\n<<<TEXT\n%s\nTEXT>>>\n\n%s" % (
        title, page_title(result)[0], result.get("text") or "", AGAIN % (first.get("quote"),))
    said["asked_again"] = _now()
    reply, _usage, _name = reader.ask(READER, SYSTEM, user, purpose="quote a rating's scale from one web page",
                                      fact_classes=("product",))
    said["rating_second"] = _parse(reply).get("rating")  # judged by `effective` on every load
    return said


def pages_of(found, to_read=False):
    """Each page once across a product's searches: [(entry, result)]. To show: the copy the reader has read, the
    longest of those; to read: the copy with the most text (so a longer copy fetched later is read too)."""
    best = {}
    for entry in found:
        for result in entry["reply"].get("results", []):
            url = result.get("url")
            if not url:
                continue
            read = (entry["proposals"].get(url) or {}).get("asked") == ASKED
            size = len(result.get("text") or "")
            rank = (size, read) if to_read else (read, size)
            if url not in best or rank > best[url][0]:
                best[url] = (rank, entry, result)
    return [(entry, result) for _rank, entry, result in best.values()]


def read_pages(title, found):
    """Ask the reader about every page that names the product and has no proposal yet; save what it said.
    Returns the errors of this run (a failed page is asked again next time; it is never filled in)."""
    found = [found] if isinstance(found, dict) else found
    pages = [(e, r) for e, r in pages_of(found, to_read=True) if names_product(title, r)[0] and (r.get("text") or "").strip()]
    todo = [(propose, e, r) for e, r in pages if (e["proposals"].get(r["url"]) or {}).get("asked") != ASKED]
    todo += [(lambda t, r, e=e: quote_again(t, r, e["proposals"][r["url"]]), e, r) for e, r in pages
             if (e["proposals"].get(r["url"]) or {}).get("asked") == ASKED
             and not e["proposals"][r["url"]].get("asked_again") and lacks_scale(e["proposals"][r["url"]], r)]
    errors = {}
    if not todo or config.mode() != "live":
        return errors
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(job, title, r): (e, r["url"]) for job, e, r in todo}
        for job in concurrent.futures.as_completed(jobs):
            entry, url = jobs[job]
            try:
                entry["proposals"][url] = job.result()
            except Exception as error:  # noqa: BLE001  (shown in the reply, never hidden)
                errors[url] = "%s: %s" % (type(error).__name__, str(error)[:160])
    for entry in {id(e): e for _job, e, _r in todo}.values():
        _save(title, {k: v for k, v in entry.items() if k != "from_cache"})
    return errors


# --- per product, per line ----------------------------------------------------------------------------------

def product_reviews(title, store=None, errors=None):
    """Everything kept for one product from its cached searches, checked again by code when the cache changes."""
    found = entries(title)
    key = (title, store)
    with _ilock:
        if errors is None and key in _index["memo"]:
            return _index["memo"][key]
    query = query_for(title)
    if not found:
        return {"found": False, "searched": False, "query": query, "rating": None, "out_of": None, "review_count": None,
                "rating_site": None, "independent": None, "rating_from": None,
                "sentence": None, "sources": [], "dropped": [], "note": "not searched yet"}
    pages, sources, dropped = [], [], []
    entry = found[-1]
    for entry_of_page, result in pages_of(found):
        url, text = result.get("url"), result.get("text") or ""
        site = site_of(url)
        ok, reason = names_product(title, result)
        if not ok:
            dropped.append({"url": url, "site": site, "reason": reason})
            continue
        said = entry_of_page["proposals"].get(url)
        if said is None:
            dropped.append({"url": url, "site": site, "reason": "the reader has not read this page"
                            + ((" (%s)" % errors[url]) if errors and url in errors else "")})
            continue
        proposal = effective(said, text)
        if not any(isinstance(proposal.get(k), dict) for k in ("rating", "review_count", "sentence")):
            dropped.append({"url": url, "site": site, "reason": "the page states no rating, count or reviewer sentence"})
            continue
        ok, reason = rates_product(title, proposal, result)
        if not ok:
            dropped.append({"url": url, "site": site, "reason": reason})
            continue
        rated_as = reason
        kept, lost = check(proposal, text)
        for d in lost:
            dropped.append({"url": url, "site": site, "what": d["what"], "reason": d["reason"]})
        if not kept:
            if not lost:
                dropped.append({"url": url, "site": site, "reason": "the page states no rating, count or reviewer sentence"})
            continue
        shown, _ = page_title(result)
        own = same_seller(site, store)
        matched_by = "the seller's own page" if own else "name only: the page calls it %r" % rated_as[:120]
        page = {"site": site, "url": url, "page_title": shown, "rated_as": rated_as, "fetched_at": entry_of_page["fetched_at"], "kept": kept,
                "seller_page": own, "sellers_own_page": own, "matched_by": matched_by}
        pages.append(page)
        for what, span in kept.items():
            sources.append({"site": site, "url": url, "page_title": shown, "rated_as": rated_as, "what": what, "quote": span["quote"],
                            "start": span["start"], "end": span["end"], "value": span.get("value"),
                            "out_of": span.get("out_of"), "fetched_at": entry_of_page["fetched_at"],
                            "span_found_in_text": True, "seller_page": own, "sellers_own_page": own, "matched_by": matched_by})
    out = {"found": bool(sources), "searched": True, "query": query, "fetched_at": entry["fetched_at"],
           "rating": None, "out_of": None, "review_count": None, "rating_site": None, "independent": None,
           "rating_from": None, "sentence": None,
           "sources": sources, "dropped": dropped, "reader": entry.get("reader"), "key_used": entry.get("key_used"),
           "ledger_row": (entry.get("ledger") or {}).get("n"), "queries": [e["query"] for e in found],
           "pages_returned": len(pages_of(found)), "ratings_by_source": [], "sources_disagree": False, "combined_how": COMBINE % MINIMUM_REVIEWS}
    # the headline: the page that states both a rating and how many reviews it rests on, most reviews first
    # (a rating whose scale is stated comes before one whose scale is not)
    def orderable(p):
        return p["kept"]["rating"]["out_of"] == 5 and p["kept"].get("review_count", {}).get("value", 0) >= MINIMUM_REVIEWS

    alone = sorted((p for p in pages if "rating" in p["kept"]),
                   key=lambda p: (not orderable(p), p["kept"]["rating"]["out_of"] is None, "review_count" not in p["kept"],
                                  p["seller_page"], -p["kept"].get("review_count", {}).get("value", 0), p["site"], p["url"]))
    head = alone[0] if alone else None
    out["ratings_by_source"] = [{"site": p["site"], "url": p["url"], "rating": p["kept"]["rating"]["value"],
                                 "out_of": p["kept"]["rating"]["out_of"], "quote": p["kept"]["rating"]["quote"],
                                 "review_count": p["kept"].get("review_count", {}).get("value"),
                                 "independent": not p["seller_page"], "seller_page": p["seller_page"],
                                 "can_be_ordered": orderable(p), "shown_as_the_products_rating": p is head} for p in alone]
    out["sources_disagree"] = len({(p["kept"]["rating"]["value"], p["kept"]["rating"]["out_of"]) for p in alone}) > 1
    if head:
        r = head["kept"]["rating"]
        n = head["kept"].get("review_count", {}).get("value")
        out.update(rating=r["value"], out_of=r["out_of"], review_count=n, rating_site=head["site"],
                   independent=not head["seller_page"],
                   rating_from="the seller's own page" if head["seller_page"] else "another site")
    said = next((p for p in ([head] if head else []) + pages if "sentence" in p["kept"]), None)
    if said:
        out["sentence"] = {"quote": said["kept"]["sentence"]["quote"], "site": said["site"], "url": said["url"],
                           "said_by": said["kept"]["sentence"]["said_by"]}
    out["note"] = _note(out, head, len(alone))
    if errors is None:
        with _ilock:
            _index["memo"][key] = out
    return out


def _note(out, head, rating_sites):
    if not out["found"]:
        return "no reviews found"
    if head is None:
        return "no rating found; a reviewer's sentence only"
    own = " (%s)" % head["matched_by"]
    count = ("from %d review%s" % (out["review_count"], "" if out["review_count"] == 1 else "s")
             if out["review_count"] is not None else "the page does not state how many reviews")
    more = "" if rating_sites <= 1 else "; %d sources state a rating, each is listed, none is averaged" % rating_sites
    scale = ("out of %g" % out["out_of"]) if out["out_of"] is not None else "(the page does not state the scale)"
    return "%g %s, %s, on one site: %s%s%s" % (out["rating"], scale, count, head["site"], own, more)


RATINGS_RULE = ("a product has a rating here only when code found, on a page that names it, an exact quote that "
                "writes the rating and the scale of five, and a quoted count of at least %d reviews" % MINIMUM_REVIEWS)


def rankable(row):
    """A candidate's reviews can order it: a quoted rating out of five and at least the minimum of quoted reviews."""
    return row.get("rating") is not None and row.get("out_of") == 5 and (row.get("review_count") or 0) >= MINIMUM_REVIEWS


INDEPENDENT = ("independent: true when the page the rating is quoted from is on another site than the store selling "
               "the product (registered domains compared); false when it is the seller's own page, a different kind "
               "of evidence. It is stated, and it does not change the ordering.")
NO_SCALE = "rating without a stated scale: not used for ordering"


def ordering(row):
    """Whether a candidate's quoted rating is used for ordering, and the reason when it is not: the same test
    `ratings()` applies, in words, so the screen and the engine tell one story."""
    if rankable(row):
        return {"used": True, "reason": None}
    if row.get("rating") is None:
        return {"used": False, "reason": "no quoted rating" if row.get("searched") else "not searched yet"}
    if row.get("out_of") is None:
        return {"used": False, "reason": NO_SCALE}
    if row.get("out_of") != 5:
        return {"used": False, "reason": "rating on a scale of %g, not of five: not used for ordering" % row["out_of"]}
    if row.get("review_count") is None:
        return {"used": False, "reason": "rating without a stated number of reviews: not used for ordering"}
    return {"used": False, "reason": "rating from %d review%s, under the minimum of %d: not used for ordering" % (
        row["review_count"], "" if row["review_count"] == 1 else "s", MINIMUM_REVIEWS)}


def ratings(line_id, line=None):
    """{candidate_id: {"rating": float, "out_of": 5, "review_count": int}} for one line, from the cache only."""
    if line is None:
        from signoff.engine import state as engine
        line = next((l for l in engine.get_state().get("lines", []) if l.get("line_id") == line_id), None)
    return for_line(line)["ratings"] if line else {}


def passing(line):
    """Every candidate of a line that passes every rule (the ones the shopper may choose), cheapest first."""
    inside = [c for c in line.get("candidates", []) if c.get("status") == "inside"]
    inside.sort(key=lambda c: (c["product"].get("price_cents") or 0, c["id"]))
    return inside


def _line(state, line_id):
    line = next((l for l in state.get("lines", []) if l.get("line_id") == line_id), None)
    if line is None:
        raise LookupError("no line %r on this sheet" % (line_id,))
    return line


def for_line(line, errors=None):
    """The reply for one line: per passing candidate what was found, and which one is best reviewed."""
    rows = []
    for c in passing(line):
        p = c["product"]
        got = product_reviews(p["title"], p.get("store"), errors)
        rows.append(dict(got, candidate_id=c["id"], store=p.get("store"), title=p["title"],
                         variant_title=p.get("variant_title"), price_cents=p.get("price_cents"),
                         picked=bool(c.get("picked")), ordering=ordering(got)))
    eligible = [r for r in rows if rankable(r)]
    eligible.sort(key=lambda r: (-r["rating"], -r["review_count"], r["price_cents"] or 0, r["candidate_id"]))
    best = None
    if eligible:
        b = eligible[0]
        best = {"candidate_id": b["candidate_id"], "title": b["title"], "store": b["store"], "price_cents": b["price_cents"],
                "rating": b["rating"], "out_of": b["out_of"], "review_count": b["review_count"], "site": b["rating_site"],
                "independent": b["independent"], "rating_from": b["rating_from"],
                "is_the_current_pick": b["picked"],
                "why": "%s; the highest among the %d passing product%s with a quoted rating out of five and at least %d reviews" % (
                    b["note"], len(eligible), "" if len(eligible) == 1 else "s", MINIMUM_REVIEWS),
                "to_take_it": {"method": "POST", "path": "/api/shopper/choose",
                               "body": {"line_id": line["line_id"], "candidate_id": b["candidate_id"]}}}
    searched = [r for r in rows if r["searched"]]
    return {"line_id": line["line_id"], "need": line.get("need"), "candidates": rows,
            "ratings": {r["candidate_id"]: {"rating": float(r["rating"]), "out_of": 5, "review_count": int(r["review_count"]),
                                            "independent": r["independent"], "site": r["rating_site"]}
                        for r in eligible},
            "ratings_rule": RATINGS_RULE,
            "best_reviewed": best,
            "best_reviewed_reason": None if best else (
                "no passing product has a quoted rating out of five with at least %d reviews" % MINIMUM_REVIEWS if searched
                else "not searched yet"),
            "summary": {"passing_considered": len(rows), "searched": len(searched),
                        "with_reviews": sum(1 for r in rows if r["found"]),
                        "with_a_rating": sum(1 for r in rows if r["rating"] is not None),
                        "used_for_ordering": len(eligible),
                        "used_for_ordering_from_another_site": sum(1 for r in eligible if r["independent"]),
                        "used_for_ordering_from_the_sellers_own_page": sum(1 for r in eligible if not r["independent"]),
                        "independent_means": INDEPENDENT,
                        "with_a_rating_not_used_for_ordering": sum(1 for r in rows if r["rating"] is not None and not rankable(r)),
                        "no_reviews_found": sum(1 for r in searched if not r["found"]),
                        "minimum_reviews": MINIMUM_REVIEWS, "tie_break": TIE_BREAK, "name_rule": NAME_RULE,
                        "limit_of_the_name_rule": LIMIT,
                        "applied": False,
                        "says": "Reviews are other people's claims on other sites. They never change whether a "
                                "product passes the order and never change the pick; the shopper may choose the "
                                "best reviewed product herself."}}


def fetch_product(title):
    """Every query form for one product (cached ones are not sent again), then the reader on its pages."""
    found, searches, errors = [], [], {}
    known = {e["file"] for e in entries(title)}
    for query in queries_for(title):
        try:
            entry = search(title, query)
        except Exception as error:  # noqa: BLE001  (shown in the reply, never hidden)
            searches.append({"query": query, "error": "%s: %s" % (type(error).__name__, str(error)[:160])})
            continue
        if entry is None:
            searches.append({"query": query, "skipped": "replay mode: nothing is fetched"})
            continue
        found.append(entry)
        searches.append({"query": entry["query"], "from_cache": bool(entry.get("from_cache")), "key_used": entry.get("key_used"),
                         "keys_refused": entry.get("keys_refused") or [], "results": len(entry["reply"].get("results", [])),
                         "cost_dollars": (entry["reply"].get("costDollars") or {}).get("total"),
                         "ledger_row": (entry.get("ledger") or {}).get("n")})
    found += [e for e in entries(title) if e["file"] in known and e["file"] not in {f["file"] for f in found}]
    if found:
        errors = read_pages(title, found)
    return searches, errors


def fetch(state, line_id):
    """Search and read for every passing product of one line (a few products at a time), then the line's reply."""
    line = _line(state, line_id)
    errors, searches = {}, []
    titles = list(dict.fromkeys(c["product"]["title"] for c in passing(line)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for made, failed in pool.map(fetch_product, titles):
            searches += made
            errors.update(failed)
    return dict(for_line(line, errors), searches=searches, reader_errors=errors)


def _payload_hash(payload):
    """The SHA-256 the ledger takes of a payload (signoff/obs/egress.py serialises it the same way)."""
    text = json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


def log(state=None):
    """Every search made, oldest first: what was sent, the ledger's row for it, and what code kept and dropped."""
    serves = {}
    for line in (state or {}).get("lines", []):
        for c in passing(line):
            serves.setdefault(c["product"]["title"], {"line_id": line["line_id"], "candidate_ids": []})["candidate_ids"].append(c["id"])
    out = []
    for title, found in entries().items():
        got = product_reviews(title)
        for entry in found:
            sent = entry.get("sent") or {}
            out.append({"step": "Reviews read", "at": entry["fetched_at"], "service": entry.get("service"), "query": entry["query"],
                        "sent": sent, "sent_is_only_the_product_title_and_review": sent.get("query") in queries_for(title)
                        and set(sent) == {"query", "numResults", "contents"},
                        "ledger": entry.get("ledger"), "ledger_is": "the outbound ledger's row, written by the process that made the search "
                        "(a search answered from the cache sends nothing and adds no row)",
                        "sent_matches_the_ledger_hash": _payload_hash(sent) == (entry.get("ledger") or {}).get("payload_sha256"),
                        "key_used": entry.get("key_used"),
                        "pages_returned": len(entry["reply"].get("results", [])),
                        "pages_read": len(entry.get("proposals") or {}), "product_quotes_kept": len(got["sources"]),
                        "product_found": got["found"], "product_note": got["note"],
                        "cost_dollars": (entry["reply"].get("costDollars") or {}).get("total"),
                        "serves": serves.get(title)})
    out.sort(key=lambda e: e["at"])
    return out
