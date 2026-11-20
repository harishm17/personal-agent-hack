# Stream REVIEWS

You are the REVIEWS stream at a timed hackathon (deadline 16:30 today; feature freeze 15:00). Use the
hackathon-stream skill. First run `./hk own REVIEWS`. Then read CONTRACT.md (skim the body; read "Rules
code decides" and the amendments from 13:10 on), OPEN.md (your items are R1 to R3) and the AGENTS.md quirks
log. **Time box: R1 and R2 on your branch by 14:40, R3 by 14:50. Anything later is cut.** Say in
NOTES/INTEGRATOR.md by 14:25 if that will not hold and what the smallest honest version is.

## Why this stream exists
The builder asked why the agent always takes the cheapest product that passes: "sometimes they might want
best quality or best value, and in this case web search and reviews matter, no?" He is right, and the
stores' own data carries no ratings (checked on every raw reply). He has supplied a web search key. The
product ("Sign-Off") shops real stores to another person's written order and "buys nothing it cannot
quote": a store's figure counts only as an exact quote found in the store's text. Reviews must obey the
same rule, and they are a weaker kind of evidence: someone else's claim, on someone else's site.

## What to build
1. **Find and quote (R1).** `signoff/reviews/`: for an item of the active sheet, take the candidates that
   pass every rule (from `signoff.engine.state.get_state()`; at most the six cheapest), and for each one
   search the web for reviews of that product with Exa (`POST https://api.exa.ai/search`, header
   `x-api-key: <EXA_API_KEY from the keys file through signoff.config.env>`, JSON body `{"query": ...,
   "numResults": 4, "contents": {"text": {"maxCharacters": 3000}}}`; a test call at 14:07 returned review
   pages with their text for about $0.007). The query is the product's title and the word "review":
   nothing else. From each result page keep only what can be quoted exactly from the returned text: a
   rating out of five, a count of reviews, and at most one sentence a reviewer wrote, each with `quote`,
   `start`, `end`, the page's address, its site and the time fetched; code checks that every quote is in
   the text at those offsets, as the store reader does (`signoff/extract/spans.py` shows how; a small
   Superlinked SIE model or the project's reader may propose, code decides). A page that is not about
   this product (the title on the page does not name it) is dropped with the reason. A product with
   nothing quotable has "no reviews found", never a guess. Cache every reply under `data/reviews/` by
   product and query so nothing is fetched twice and replay mode needs no network; space calls out.
2. **Offer, do not decide (R2).** `signoff/reviews/api.py` exporting `router` (optional in the app, already
   listed): `GET /api/reviews?line_id=` returns per candidate `{rating, out_of, review_count, sentence,
   sources: [{site, url, quote, fetched_at}], found}` and a summary; `POST /api/reviews/fetch {line_id}`
   (laptop only; the prefix is guarded) runs the search for that item. Reviews never change whether a
   product passes the order's rules and never change the pick by themselves. What they add is a second,
   visible ordering the shopper may use: "best reviewed among those that pass" (the highest quoted rating
   with at least a handful of reviews; state the tie-break and the minimum in the reply). The engine has,
   or is getting, `POST /api/shopper/choose {line_id, candidate_id}` so the shopper can take that product;
   you only say which one it would be and why. Tell SCREEN in NOTES/SCREEN.md the shape so a passing row
   can show "4.6 · 212 reviews · site" quietly, with the quote and link on click.
3. **In the records (R3).** Every search goes through the outbound ledger (`signoff.obs.egress(recipient,
   purpose, payload, fact_classes)`, see `signoff/obs/egress.py`) so the trail can show that the search
   service was sent a product name and nothing else: no limit, no measurement, no person. Tell TRAIL and
   GRAPH in their NOTES files the route and shape so the step appears in the run ("Reviews read").

## You own
`signoff/reviews/**`, `tests/reviews/**`, `data/reviews/**`. Everything else: `NOTES/<OWNER>.md`. Develop on
port 8010; main is 8800 (GET only there).

## Rules
The working path is not changed: you add a route and files; you never write engine state. No special
cases, no lists of sites or products, no silent fallbacks. Say plainly in the reply when a number comes
from one site with three reviews. Tests that call Exa get `@pytest.mark.live`. No AI or tool authorship
lines in commits, docs or code. Close each item with `DONE R<n>: <proof>` or `WONTDO R<n>: <reason>` in
NOTES/INTEGRATOR.md. Commit small and often to `stream/REVIEWS`. Do the work yourself; start no new threads.
