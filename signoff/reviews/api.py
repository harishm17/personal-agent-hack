"""Routes of the REVIEWS stream. The GET routes are open and read only the cache; POST /api/reviews/fetch is
laptop only (app.py guards the /api/reviews/ prefix) and is the only route that reaches the web."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from signoff.reviews import reviews

router = APIRouter()


class Fetch(BaseModel):
    line_id: str


def _state():
    from signoff.engine import state as engine
    return engine.get_state()


@router.get("/api/reviews")
def read(line_id: str | None = None):
    """What was found for the passing candidates of one line (or of every line), from the cache. Each candidate:
    {rating, out_of, review_count, sentence, sources: [{site, url, quote, fetched_at, ...}], found}; plus which
    passing product is best reviewed and why. Nothing here changes a status or a pick."""
    state = _state()
    try:
        lines = [reviews._line(state, line_id)] if line_id else state.get("lines", [])
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    out = [reviews.for_line(line) for line in lines]
    if line_id:
        return out[0]
    short = ("found", "searched", "rating", "out_of", "review_count", "rating_site", "sentence", "note", "ordering")
    return {"sheet": (state.get("sheet") or {}).get("id"), "lines": out, "minimum_reviews": reviews.MINIMUM_REVIEWS,
            "ratings_rule": reviews.RATINGS_RULE,
            "ratings": {cid: r for line in out for cid, r in line["ratings"].items()},
            "by_candidate": {c["candidate_id"]: dict({k: c.get(k) for k in short}, line_id=line["line_id"],
                                                     best_reviewed=bool(line["best_reviewed"]) and line["best_reviewed"]["candidate_id"] == c["candidate_id"])
                             for line in out for c in line["candidates"]}}


@router.post("/api/reviews/fetch")
def fetch(body: Fetch):
    """Search the web for reviews of one line's passing products (cached ones are not fetched again) and read them."""
    try:
        return reviews.fetch(_state(), body.line_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/api/reviews/log")
def log():
    """The step "Reviews read" for the run's records: every search, what was sent, and its row in the outbound ledger."""
    searches = reviews.log(_state())
    return {"step": "Reviews read", "recipient": reviews.RECIPIENT, "searches": searches,
            "sent_only_product_titles": all(s["sent_is_only_the_product_title_and_review"] for s in searches),
            "sealed_values_found_in_any_search": sorted({hit for s in searches for hit in (s.get("ledger") or {}).get("sealed_found_in_payload") or []})}
