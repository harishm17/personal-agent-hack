"""The REVIEWS stream: what the web says about the products that pass, kept only as exact quotes with their source."""

MINIMUM_REVIEWS = 5


def ratings(line_id, line=None):
    """For the engine's orderings, one line: {candidate_id: {"rating": float, "out_of": 5, "review_count": int,
    "independent": bool, "site": str}}. `independent` is false when the rating is quoted from the seller's own page
    (the review page's registered domain is the product's store) and true when it is on another site; `site` is
    the page's site. It describes the evidence and does not change which candidates appear.

    From the cache under data/reviews/ only: it never touches the network, and returns {} when nothing is cached
    (or the line does not exist). A candidate appears only when all of this holds: it passes the order's rules and
    is among the six cheapest that do (only those are ever searched); a page that names the product states its
    rating out of five as an exact quote that code found in the page's text, with the rating and the scale both
    written in the quote; and the same page states, in a quote code found, a count of at least MINIMUM_REVIEWS (5)
    reviews. A rating whose page writes no scale, or fewer than five reviews, is left out; nothing is filled in.
    A candidate that is absent has no usable rating: order it after those that have one, never as zero.

    `line` (optional) is the engine's own line dict (`line_id`, `candidates` with `id`, `status`, `product`); pass it
    when calling from inside the engine so the state is not read again. Without it the line is looked up in
    `signoff.engine.state.get_state()`. Reviews never change a status; this function only reads.
    """
    from signoff.reviews import reviews
    return reviews.ratings(line_id, line)
