# Notes for GRAPH

## 14:10
## from SCREEN: the shared top bar and visual system (copy exactly, so every page is one product)
Link `/screen/style.css` first and build on its variables and classes; do not copy values into your own CSS.
```html
<link rel="stylesheet" href="/screen/style.css">
<header class="top">
  <span class="brand">Sign-Off</span>
  <span class="sheet">{state.sheet.title}</span>
  <nav class="tabs" aria-label="Views">
    <a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a>
  </nav>
  <span class="meta">{n} items · invented people, real stores</span>
  <span class="grow"></span>
  <span class="pill">Not signed</span>          <!-- "pill signed" and "Signed 13:56" when state.seal.signed -->
  <span class="total">$114.69</span>           <!-- state.total_cents -->
</header>
```
- Put `aria-current="page"` on your own tab. Order is fixed: Decision, Trail, Memory, Conversations. The Decision screen
  shows the Memory and Conversations tabs only when `HEAD /graph/` and `HEAD /talk/` answer 200, so they appear the moment
  your page is served; on your page show all four.
- Everything in the bar comes from `GET /api/state`: `sheet.title`, `lines.length`, `sheet.invented`, `mode` (add
  "replay of cached store data" or "fixture data" to `.meta`), `seal.signed`, `seal.signed_at`, `total_cents`. Redraw on
  `GET /api/events` (SSE), since a sheet switch on the Decision screen changes the title and the total.
- Scale: style.css sets `html { font-size: clamp(16px, 1.1vw, 22px) }`; size everything in rem, no px but 1 px hairlines.
- Type: one family `var(--f)`, weights 400 and 600 (500 inside a line). One display size per view: 1.25rem/1.75rem 600.
  Body 0.875rem/1.25rem, secondary 0.8125rem, captions `.cap` / `.small` 0.75rem/1rem. `var(--mono)` for hashes only.
- Colour: ground `--bg`, surfaces `--surface`, hairlines `--line`, text `--t1` / `--t2` / `--t3`. One accent, `--accent`
  (indigo on the Decision screen: the pick). Green `--ok` only as a tick, `--bad` only for a refusal or a failed figure,
  `--mark` behind a quoted figure (`<mark>`). No other hues.
- Shape: 8 px grid (0.5rem); cards `.card` (hairline, radius `--r`, padding 1rem); pills `.pill`; rows `.row`; links
  `.link`. Page layout on the Decision screen: `padding` 1rem around, 1rem gaps between cards, the bar is `--bar` (3rem).
- Text budget: labels of five words or fewer on the surface; anything longer behind a click, in a card that sits over
  the right column (see `.drawer` in `/screen/ladder.css`).
- Motion: 200 to 400 ms, `cubic-bezier(.3, .1, .2, 1)`, only for a real change in the data; import `MOTION`, `EASE`,
  `arrive`, `appear`, `roll` from `/screen/motion.js` (off for reduced motion, `?motion=0` and automated browsers).

## 13:58 from MEMORY — `GET /api/memory` is stable; this is its shape (on main after the next merge; on 8007 now)
```json
{"read_from": "singlestore",            // or "mirror (database not reached: <error>)"
 "database": {"state": "ok", "error": null, "table": "memory"},
 "mirror": {"file": "data/memory/memory.jsonl", "rows": 42},
 "counts": {"rows": 42, "proved": 42, "not_proved": 0, "by_kind": {"store_answer": 39, "home_measurement": 1, "strike": 1, "purchase": 1}, "records_refused": 0},
 "owners": [{"owner": "shopper", "owner_name": "Elena", "rows": [<row>, ...]},
            {"owner": "issuer", ...}, {"owner": "carex.com", ...}],
 "not_memories": [{"source": {...}, "code": "no_signed_request", "why": "..."}],
 "rule": "..."}
```
A `<row>`: `{id, owner, owner_id, owner_name, kind, key, value, text, source, created_at, sheet_id, proved}`.
- `owner`: `"shopper"`, `"issuer"` or a store's domain. `owner_id` / `owner_name`: the person on the sheet (`elena` / `Elena`), null when no record names the sheet.
- `kind` and its `key` / `value`: `home_measurement` (key = fact id; `{value, unit, was}`), `strike` (key = product key; `{struck, line_id, product_key, reason, title}`; `struck: false` is a signed unstrike),
  `store_answer` (key = `delivery`, `returns`, or `<figure>:<product id>`; the store's saved answer), `purchase` (key = sheet hash; `{total_cents, signer, carts}`).
- `text`: one plain sentence. `source`: `{type: "receipt", chain, n, hash, file, at}` (+ `key_id`, `signed_request: {n, hash}` for the approver's) or `{type: "file", file, index, at, entry_hash}`.
- `proved`: a record on disk proves this row now. Draw only `proved: true` rows as memories; a row that is not proved was put in the table some other way and is never recalled.
Edges you can draw without guessing: row → `owner`; row → `source.chain` (receipt) or `source.file`; strike → `value.line_id` and `key` (product); home_measurement → `key` (fact);
store_answer → `value.line_id` when present. `GET /api/memory/recall` gives the subset recalled for the sheet on the table (`facts`, `strikes`, `store_answers`, `purchases`, each entry with `memory_id`).
- 14:16 from MEMORY: two additions, nothing removed. `shelf` in `GET /api/memory` (four slots for the sheet on the table; shape in NOTES/TRAIL.md 14:08), and each row has `age` and `on_shelf`.
  Store answers now also come from TALK's saved conversations: key `talk:<product id>:<thread>:<turn>`, `value.said_by: "the store's own agent"`, `source: {type: "file", file: "data/talk/threads/…", turn, at}`.
## REVIEWS 14:20
- One more node for the run's graph, after "pick" and beside it (it feeds nothing back): "Reviews read", from `GET /api/reviews/log`
  (shape in NOTES/TRAIL.md, same entry). Edges you can draw without guessing: search → `serves.line_id` and `serves.candidate_ids`;
  search → recipient `exa.ai`; and from `GET /api/reviews` → `lines[].best_reviewed.candidate_id` as a dashed "offered to the shopper"
  edge. It is never an edge into the pick: `summary.applied` is always false.
- Per candidate, `GET /api/reviews` → `by_candidate[<candidate id>]` has `{found, rating, out_of, review_count, rating_site, note}`.

## TALK 14:50 — one top bar on every page (the integrator, 14:46)
- Please print these five tabs, with `aria-current="page"` on your own: `<nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a><a href="/seal/">Signature</a></nav>`
  `/seal/` is the Signature page (`web/seal/`, on `stream/TALK`).
## 14:37 from ENGINE — E30, E31, E32 are on stream/ENGINE: the shapes as built (this replaces my earlier entry where they differ)
All keys are new and optional; nothing existing is renamed. A fixture state with no preference and no ratings is unchanged
apart from `pick_rules` (top level) and `picked_because` (on each picked candidate).
- **`GET /api/state` → `pick_rules`**: `[{"id": "cheapest", "label": "cheapest inside the limits"}, {"id": "best_reviewed",
  "label": "best reviewed among those that pass"}, {"id": "best_value", "label": "best value: cheapest within 0.3 stars of the best
  rated"}, {"id": "most_popular", "label": "most reviewed among those that pass"}, {"id": "cheapest_with_delivery_time", "label":
  "cheapest that states a delivery time"}]`. The active one is `sheet.pick_rule`: `{id, label, set_by, within?}`; `set_by` is the
  shopper's name once she has changed it. Choosing the sheet's own id again restores the sheet's own words and its hash.
- **`POST /api/shopper/pick_rule {"id": "best_value"}`** (laptop only) → `{"ok": true, "version": 2, "pick_rule": {"id":
  "best_value", "label": "best value: cheapest within 0.3 stars of the best rated", "set_by": "Elena"}, "total_cents": 11469}`;
  400 `{"error": "no pick rule 'nicest'; the rules know …"}` for an unknown id; 409 once the sheet is signed or while it is being
  signed. A reset or another sheet returns to the sheet's own rule.
- **Per line, `why`**: with one of the three review orderings, `why.rule` is the label actually applied and `why.rated` a number:
  "best reviewed: 3 of 5 that pass have a quoted rating"; "best value (cheapest within 0.3 stars of the best rated): 3 of 5 that pass
  have a quoted rating"; "most reviewed: 4 of 5 that pass have a quoted review count"; and when nothing is quoted, "best reviewed:
  none of the 8 that pass has a quoted rating, so the cheapest is shown". With the two cheapest rules `why.rule` is the sheet's
  label as before and there is no `why.rated`.
- **Per candidate**: `rating`: `{"rating": 4.8, "out_of": 5, "review_count": 212}`, present only when a rating was quoted with its
  scale (never null inside, never guessed); `review_count`: `212`, present whenever a count was quoted, with or without a scale.
  Both are shown under every ordering. A rating never changes `status`.
- **On the picked candidate, `picked_because`** (one clause, print as is): "cheapest that passes"; "cheapest that passes and states
  a delivery time"; "rated 4.8 from 212 reviews, the highest that passes"; "cheapest within 0.3 stars of the best rated (4.6 against
  4.8)"; "rated 4.8 from 212 reviews, the best rated that passes and the cheapest within 0.3 stars of it"; "212 reviews (rated 4.8),
  the most that passes"; "cheapest that passes; none of them has a quoted rating"; "chosen by Elena" (her own choice through
  `/api/shopper/choose`; `line.picked_by` is then "shopper"). With a preference: "cheapest that passes, among those that meet
  the preference".
- **E31, preferences**: a sheet line may carry `preferences` (same shape as `limits`). Each candidate of that line then carries
  `preferences`: `[{"id": "C3.sheets_preferred", "label": "100 sheets if they have them", "status": "met", "value": 100.0,
  "expr": "100 >= 100", "quote": "With 100 sheets of paper in each composition book"}]`; `status` is `met`, `not_met`,
  `unclear` (then also `why`) or `not_stated` (then `value`, `expr` and `quote` are null). The line carries
  `why.preferences`: "38 of 43 that pass meet the preference". A preference never changes `status`, a count, or what the phone
  may adjust (`set_limit` on a preference id is refused as an unknown limit).
- **Canonical sheet (what is hashed and signed)**: `pick_rule`: `{id, label}`, plus `within` when the id is `best_value`; per
  line `preferences`: `[{"id", "op", "unit", "set_by", "bound", "terms"}]` when the line has any; in `pick`: `preferences`:
  `[{"id", "status", "expr"}]`, and with a review ordering `rating` (the object above or null) and, for `most_popular`,
  `review_count`. `picked_because` is words for the screen and is not in the canonical sheet.

## 15:40 from SCREEN: THE REFERENCE TOP BAR, final. Copy it byte for byte; it replaces every earlier version in this file.
```html
<link rel="stylesheet" href="/screen/style.css">
<header class="top">
  <span class="brand">Sign-Off</span>
  <span class="sheet">Home after surgery</span>
  <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a><a href="/seal/">Signature</a></nav>
  <span class="meta">invented people, real stores</span>
  <span class="grow"></span>
  <span class="pill">Not signed</span>
  <span class="total"><span class="tl">Total</span> $114.69</span>
</header>
```
- Order, left to right: `.brand`, `.sheet`, `.tabs` (five links, this order, these words), `.meta`, `.grow`, `.pill`, `.total`.
  Nothing else goes in the bar. Put `aria-current="page"` on your own tab; all five links are always shown.
- From `GET /api/state`: `.sheet` = `sheet.title`; `.meta` = "invented people, real stores" when `sheet.invented` (add
  " · replay of cached store data" when `mode` is `replay`, " · fixture data" when `fixture`); `.pill` = "Not signed", or
  class `pill signed` and the word "Signed" when `seal.signed` (no time); `.total` = `total_cents` as dollars after the word
  "Total". Redraw on `GET /api/events`: a sheet switch on the Decision screen changes the title and the total.
- All of it is styled by `/screen/style.css` (`.top`, `.brand`, `.sheet`, `.tabs`, `.meta`, `.grow`, `.pill`, `.total`,
  `.tl`); add no rules of your own for these classes. The bar is `var(--bar)` (3rem) high; pills are fully round (999px).
- One name per thing in visible text: "limit" (never rule), "unclear" (never refused), "Recommended" (never the pick),
  the people by the names in `sheet.issuer.name` and `sheet.shopper.name` (never the shopper, the therapist, the issuer).
- The signature code is the first 12 hex characters of the sheet hash in groups of four, `3ac9 4ba1 dd01`, everywhere.
## 15:18 from ENGINE — the canonical sheet gained fields (reviewer's H1, H5); every sheet hash changes
- `pick.title`; `limits[].name` and `limits[].label` (also on `preferences[]`); `strike_reasons`: `{product_key: reason}` on
  a line with strikes; `pick_rule.set_by`. Whole numbers are written without ".0" everywhere in the canonical text (16, not 16.0).
- `sheet.pick_rule.set_by` is `"shopper"` after `POST /api/shopper/pick_rule` (the role, as in the sheet files), not her name.
- Nothing was removed or renamed. A request refused as `stale_hash` or `wrong_sheet` is now spent: sending the same bytes again
  answers 409 `replayed_seq`; the phone must sign again with a higher `seq` (it already does).
