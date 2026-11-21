
## 11:32 from ENGINE
- `/api/state` is live from the real pool on main. New optional keys, nothing renamed: `sheet_hash`; `seal.current`, `seal.signer`,
  `seal.signed_at`; `readers` (which reader decided and how far the others agree: use the word "agreement", never "accuracy").
- A figure may carry `unsure: true` with `unsure_reason` (it does not count: the candidate is `not_stated` and `reason` says why),
  `agreed_by` (readers that give the same number), `also_marked_by` (SIE extract marked the same span) and `span_match`.
- A candidate's `reason` for `not_stated` now has three forms: "<figure> never stated on the page", "<figure> quote not found in the
  store's text", "<figure> stated, but not clearly for this product: <why>".
- `POST /api/shopper/say {text}` → `{reply, refused, tool_calls, intent, decided_by, state_unchanged, seconds}`. A plain request for a
  change ("put it back") answers at once; a question takes 3 to 5 s, so show a waiting state.
- After signing, `POST /api/shopper/fact` answers 409 `{"error": ...}`: the signed sheet is frozen until reset.

## 11:36 from ENGINE — answers to your 11:30 note in NOTES/ENGINE.md
- Done: `POST /api/shopper/say` always answers 200 with `{reply, refused, tool_calls}` (the 500 was the chat module not being merged
  yet). "Raise the weight limit to 500 lb please" → `refused: true` in 0 s, written by code. If the model cannot be reached a question
  gets a plain "I can't reach my model" reply, `refused: false`.
- Done: every found figure, and every store term in `checks[].terms`, carries `sentence` and `quote_in_sentence: [a, b]`, with
  `sentence[a:b] == quote`. The sentence is the store's own text around the span (cut at word ends with "…" when the store wrote
  no full stop for 260 characters; spec lists often have none).
- The seal keys you read are kept as they are.

## 12:52 from TRAIL — the feed for your stepper's drawers: `GET /api/trail` (stable; on branch stream/TRAIL, commit 5ea1d9b)
Read-only, never raises, `Cache-Control: no-store`. Refetch on the `/api/events` signal (ledger rows do not bump the state
version, so the trail page also polls every 5 s).
```
{ sheet: {id, title, invented, items}, mode, state_version, signed, signed_at,
  kinds: ["evidence","reading","check","approval","action"],
  steps: [ { id, n (1..7), label, sub, done, events, records, kinds: {evidence: n, ...}, receipts, refused,
             first_at, last_at, duration_ms } x 7 ],
  events: [ { n, at, end_at, t (epoch ms), step, own_step, kind, mark, lane, to_lane, label, detail, ref,
              duration_ms, count, verified, verified_count, stopped, facts, source, receipt, hash,
              items: [ {title, quote, source, link, about, status, price, by, hash, prev_hash, body_hash, receipt, ledger, bytes} ],
              more } ],
  chain: [ {n, at, type, hash, prev_hash, verified} ],
  summary: {events, records, kinds: {...}, messages_out, to_stores, limits_to_stores, blocked, receipts, receipts_verified},
  sources: [ {id, ok, note?} ] }
```
- Step ids, in order: `list_read`, `stores_searched`, `pages_read`, `checked`, `picked`, `signs`, `carts`. `steps[i].label` is ready
  to show ("List read" ... "<issuer name> signs", "Carts"); `sub` is the few words under it, read from the state's counts
  ("5 limits, quoted", "4 stores", "not signed", "none exist"); `done` drives the tick.
- A drawer for one step: `events.filter(e => e.step === id)`, already in order. One line per event: `label` (five words or
  fewer), `detail` (short), `at` (null when the record has no time: figures, comparisons and picks have none today),
  `receipt` + `hash` when the event is a receipt. `stopped: true` is a refusal or a blocked message. `count` records are
  inside one event; the first 30 are in `items`, the rest counted in `more`.
- `own_step: false` means a record-keeping message (Amplitude, Statsig, Airbyte, the chain start) that happened during the
  step; hide those in a small drawer if you want only the step's own events.
- `/trail/#<step id>` opens the trail page with that step open, if you want a "see all" link from a drawer.
- [ ] Tabs: please put the same two tabs in your top bar, right after the sheet title, so the bars match:
  `<nav class="tabs"><a href="/" aria-current="page">Decision</a><a href="/trail/">Trail</a></nav>`. Mine is styled in
  `web/trail/trail.css` (`.tabs`): 13 px, grey, the current one in ink with a 2 px underline at the bar's bottom edge.

## 13:09 from TRAIL — `/api/trail`: what changed since the 12:52 note (additions only; nothing renamed)
- Page now links your `/screen/style.css` and uses your top bar markup (`.brand`, `.tabs`, `.sheet`, `.meta`, `.grow`,
  `.pill`, `.total`); thank you for NOTES/TRAIL.md. The tabs request above is done on your side already.
- `sheet.total_cents` added. `steps[5].label` is now "<Issuer role> signs" ("Plumber signs"), the same words as your
  stepper; `steps[i].sub`: "5 limits, quoted", "4 stores", "179 pages", "57 inside", "$1118.75", "signed 13:07" or
  "not signed", "3 carts" or "none exist".
- Step ids stay `list_read`, `stores_searched`, `pages_read`, `checked`, `picked`, `signs`, `carts` (yours are `list`,
  `search`, `read`, `check`, `pick`, `sign`, `carts`): map by position, `feed.steps[i]` is your step `i`.
- New per event: `proof` (the words for `verified_count`: "quotes found in the text", "match the sheet", "hash and link
  hold"), `timed` ("measured" when the duration was measured by the tool-call log, "first to last" when it is the
  time between the first and last record, null when there is none). New per item: `at` (when that record was read).
- New sources: the tool-call log (`signoff.obs.recent`) gives measured times ("16 check runs · 50 ms", "3 cart requests");
  receipts written by SIGN (enrolled, persona status, senso checked) are placed by their actor.
- `summary.earlier_runs`: records of an earlier run (before the current receipt chain began) that are left out of the
  steps a reset redoes (checked, picked, signs, carts). Cached evidence and its reading are kept.
- Deep links: `/trail/#signs` opens a step; `/trail/?event=<n>#<step>` also opens that event's side sheet.

## 13:58 from TRAIL — `/api/trail` additions for T4 (context per model call); nothing renamed
- `events[].context` (ledger events only, else null), `steps[].context` (the step's model calls, else null) and
  `summary.model_calls`: `{calls, given: [{id, label, calls}], found: [{id, label, calls, matches}], not_given: [{id, label}],
  only, bytes: {min, median, max, total}, parts: [{name, calls, chars}], withheld: [{name, calls}]}`. `label` is two words
  ("page text", "the order", "limits"). `found` is a sealed value the ledger's search met in the text sent: show it, in red.

## 13:58 from MEMORY — the memory routes are stable (shape of a row and of `GET /api/memory`: NOTES/GRAPH.md, 13:58)
- `GET /api/memory/recall` → what a new run of the sheet on the table starts with: `{sheet_id, facts: [{fact_id, value, unit, measured_by, measured_at, used_by: [limit ids], age: {seconds, text}, memory_id, source, text}],
  strikes: [{line_id, product_key, title, reason, by: "issuer", by_name, at, age, memory_id, source, text}], store_answers: [{store, key, line_id, asked_at, age, memory_id, source, text}],
  purchases: [{signed_at, total_cents, carts, sheet_hash, ...}], counts: {recalled, of}, read_from, error}`.
- `GET /api/memory/recall?line_id=L5` → `{line_id, need, recalled: [{kind, owner, why, text, age, memory_id, source, ...}], counts: {recalled, of}}`: what bears on one item and why.
- What the engine applied is already in `/api/state` → `memory` and on the fact (`remembered`, `measured_by`, `measured_at`) and the strike (`from_memory: true`). A short line is enough: "remembered · Elena · 13:57", "struck before · <reason>", "asked 2 h 43 min ago".
## TALK 14:04
- `web/screen/ladder.js:233` (and TRAIL's `web/trail/trail.js:54`): please add a third tab to the top bar,
  `<a href="/talk/">Conversations</a>`. The page is `web/talk/index.html` on `stream/TALK`; it uses `/screen/style.css`
  and the same top bar, with the tabs Decision, Trail, Conversations.

## 14:25 from STORE — `GET /api/tools` rows: what each field means (S18), for the "Tools at work" drawer
Reply: `{tools: [row], absent: [{tool, why}], sheet, line_id, at}`; `?line_id=L4` picks the item the SQL rows are about (default: the first line with a pick). A row: `{tool, job (five words), number, unit, detail (one sentence),
source (route or file), ok, live, agrees, basis}`. `ok` = the source answered; it is **not** "the check passed". `live` = true when this app made the call just now or since it started, false for a saved run (SIE's pages, Firedrill's campaigns): show "saved run"
in plain words from `basis`, not a red mark. `agrees` is for the two SQL rows only (SingleStore, Airbyte): the statement's rows equal the engine's inside set / the direct answer; null elsewhere. Draw `number` + `unit` large and `detail` small. The first call after a restart
takes about ten seconds (remote database); later calls are cached for 20 s and a stale answer is returned at once and refreshed in the background.
## REVIEWS 14:20
- New, read only, no effect on any status or pick: `GET /api/reviews` (every line of the sheet on the table) and
  `GET /api/reviews?line_id=L4` (one line). Reviews exist only for candidates with `status: "inside"`, the six cheapest per line.
- Easiest for a row: `GET /api/reviews` → `by_candidate[<candidate id>]` =
  `{found, searched, rating, out_of, review_count, rating_site, sentence: {quote, site, url, said_by} | null, note, line_id, best_reviewed}`.
  Quiet line on a passing row: `4.6 · 58 reviews · parentgiving.com`. Write it from the fields, and when `out_of` is null show the
  rating without "/5" (the page did not write a scale); when `review_count` is null leave the count out. `found: false` with
  `searched: true` is "no reviews found"; `searched: false` is "not searched yet". Never fill a gap. `note` is the same thing in words.
- On click: `lines[].candidates[]` has, per candidate, `sources: [{site, url, page_title, rated_as, what: rating|review_count|sentence,
  quote, start, end, value, out_of, fetched_at, matched_by, sellers_own_page}]` and `dropped: [{site, url, reason}]`. Show the quote in
  quotation marks with its site as a link. `matched_by` is either "the seller's own page" or "name only: the page calls it '…'":
  please show it, a page on another site is matched by the product's name and nothing stronger.
- The offer: `lines[].best_reviewed` = `{candidate_id, title, store, price_cents, rating, out_of, review_count, site, is_the_current_pick,
  why, to_take_it: {method: "POST", path: "/api/shopper/choose", body: {line_id, candidate_id}}}` or null with `best_reviewed_reason`.
  It is an offer, never applied (`summary.applied` is always false): a button "Take the best reviewed instead" that posts `to_take_it.body`
  to ENGINE's route. `summary.minimum_reviews` (5), `summary.tie_break` and `summary.says` are the words to show beside it.
- Wording: "reviewers say", "the page states"; never "proves", never "best" without "reviewed". On sheet 4 today: L4 has an offer
  (Drive rollator, 4.6 of 5 from 58 reviews on the seller's own page, $119.99, not the pick); L1 and L5 have none and say why.
- `POST /api/reviews/fetch {line_id}` (laptop only) searches for a line not yet searched; about 20 s for six products, then cached.

## TALK 14:50 — one line where the signing happens, and the same short code in three places (the judge, item B)
- The line: `Dana signs: 6 limits · 8 quotes · 3 picks · $114.69` and the code `3ac9 4ba1 dd01`. Both are data:
  `GET /api/seal/proof` → `summary: {text, code, limits, quotes, picks, total_cents}` (read-only, on `stream/TALK`).
- The same from your own copy of the canonical sheet, so the phone prints what it computed itself and not what the
  server says (`c` is the parsed canonical sheet, `hash` its SHA-256 hex; on the phone these are `canon.obj`, `canon.hash`):
  ```js
  const picks = c.lines.filter((l) => l.pick), n = (k, one) => `${k} ${one}${k === 1 ? "" : "s"}`;
  const line = `${name} signs: ${n(c.lines.reduce((a, l) => a + l.limits.length, 0), "limit")} · ${n(picks.reduce((a, l) => a + l.pick.quotes.length + (l.pick.delivery.quote ? 1 : 0), 0), "quote")} · ${n(picks.length, "pick")} · $${(c.total_cents / 100).toFixed(2)}`;
  const code = hash.slice(0, 12).replace(/(.{4})(?=.)/g, "$1 ");
  ```
  quotes = each pick's figure quotes plus its delivery quote when the store stated one. `/seal/` prints the same line and code.
- For the Signature card on the decision screen: print `summary.text` and `summary.code` (or compute them from
  `/api/sheet/canonical`, which the screen can fetch).
- One top bar on every page. `web/screen/ladder.js:31`: add `["/seal/", "Signature", "signoff.seal.api"]` to `TABS` and
  `"/seal/"` to `KNOWN_PAGES`. The full markup, as `/talk/` and `/seal/` now print it:
  `<nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a><a href="/seal/">Signature</a></nav>`
## 14:27 from ENGINE — shapes for E30 (pick rule the shopper chooses) and E31 (preferences), fixed now so you can build
All keys are new and optional; nothing existing is renamed.
- **`GET /api/state` → `pick_rules`**: `[{"id": "cheapest", "label": "cheapest inside the limits"}, {"id": "best_reviewed", "label":
  "best reviewed among those that pass"}, {"id": "best_value", "label": "best value: cheapest within 0.3 stars of the best rated"},
  {"id": "cheapest_with_delivery_time", "label": "cheapest that states a delivery time"}]`. The active one is `sheet.pick_rule`
  `{id, label, set_by, within?}`.
- **`POST /api/shopper/pick_rule {"id": "best_value"}`** (laptop only) → `{ok, version, pick_rule, total_cents}`; 400 for an unknown
  id, 409 once the sheet is signed. The sheet hash changes with the rule (and with `within`).
- **Per line, `why`**: `rule` is the label actually applied, for example "best reviewed: 2 of 5 that pass have a quoted rating" or
  "best reviewed: none of the 5 that pass has a quoted rating, so the cheapest is shown"; `rated` = how many of those that pass have a
  quoted rating (only for the two rating rules).
- **Per candidate**: `rating`: `{"rating": 4.7, "out_of": 5, "review_count": 212}` or absent when the store's data quotes none;
  on the picked one, **`picked_because`**: one clause to print, for example "cheapest that passes", "rated 4.7 from 212 reviews, the
  highest that passes", "cheapest within 0.3 stars of the best rated (4.6 against 4.8)", "chosen by Elena".
- **E31, a line may carry `preferences`** (same shape as `limits`, in `sheet.lines[]`). Each candidate of such a line carries
  `preferences`: `[{"id": "C3.sheets_preferred", "label": "…", "status": "met" | "not_met" | "unclear" | "not_stated", "value": 100,
  "expr": "100 >= 100", "quote": "…"}]`. A preference never changes `status`, the counts, or what the phone may adjust. Among
  those that pass, more preferences met come first, then the pick rule. `why.preferences` says it in words ("1 of 4 that pass meet
  the preference"). The canonical sheet carries each preference with its bound, so it is signed.

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

## 15:18 from ENGINE — the canonical sheet gained fields (reviewer's H1, H5); every sheet hash changes
- `pick.title`; `limits[].name` and `limits[].label` (also on `preferences[]`); `strike_reasons`: `{product_key: reason}` on
  a line with strikes; `pick_rule.set_by`. Whole numbers are written without ".0" everywhere in the canonical text (16, not 16.0).
- `sheet.pick_rule.set_by` is `"shopper"` after `POST /api/shopper/pick_rule` (the role, as in the sheet files), not her name.
- Nothing was removed or renamed. A request refused as `stale_hash` or `wrong_sheet` is now spent: sending the same bytes again
  answers 409 `replayed_seq`; the phone must sign again with a higher `seq` (it already does).
## 15:06 from SIGN — G23, the shopper asks and the approver decides: JSON shapes (the code follows within minutes; these are the contract)
- **`POST /api/shopper/ask-change {"limit_id": "L1.capacity", "value": 250, "note": "the chair I like is rated 250"}`** (laptop only, like the rest of `/api/shopper/`) →
  `{"ok": true, "ask": ASK}`. `note` is optional text, 300 characters at most. One pending ask per limit: a new one for the same limit replaces the
  earlier one (it becomes `status: "replaced"`). It changes nothing in the sheet and nothing under the hash. Refusals, each `{"error": code, "detail": words}`:
  400 `not_an_issuer_limit` (a limit the approver does not set, or an unknown id), 400 `bad_value`, 400 `out_of_range` (outside the limit's min to max),
  400 `off_step`, 400 `no_change` (the value is the one it has now), 409 `already_signed` (also `signing in progress`).
- **ASK** (the same object everywhere):
  `{"id": "ask-3", "sheet_id": "sheet1", "limit_id": "L1.capacity", "line_id": "L1", "label": "holds at least", "unit": "lb", "op": ">=",
    "from": 300, "to": 250, "note": "…", "by": "Elena", "at": "2026-11-20T15:07:41-08:00",
    "status": "pending" | "accepted" | "declined" | "changed" | "replaced",
    "settled_at": null | iso, "settled_by": null | "Dana", "changed_to": null | number,
    "text": "Elena asks: holds at least 250 lb instead of 300 lb",
    "outcome": "asked Dana · waiting" | "Dana changed it to 250" | "Dana declined" | "Dana changed it to 275" | "replaced by a newer ask"}`
  `accepted`: she accepted the ask itself (her signed `set_limit` carries `ask_id`; the value is the asked one). `changed`: she moved that limit to another
  value herself while the ask was waiting (`changed_to`). `declined`: her signed `decline_ask`. `text` and `outcome` are words to print as they are; `by` is the
  shopper's name from the sheet, `settled_by` the name on the approver's key.
- **`GET /api/asks`** → `{"asks": [ASK, …], "pending": 1}` for the sheet that is loaded now, oldest first, pending and settled. The same list is
  `asks` inside `GET /api/issuer/status`. A reset, or another sheet, starts with none.
- Your "change" link becomes "Ask Dana" and opens a value and a note, then `POST /api/shopper/ask-change`; while an ask for that limit is pending show its
  `outcome` ("asked Dana · waiting"); when it settles show `outcome` again ("Dana changed it to 250", "Dana declined"). Poll `/api/asks` (about every 3 s)
  or read it from `/api/issuer/status`. Nothing here changes the limit: only the approver's signed request does, and the chain has a receipt for the
  ask (`limit_change_asked`, actor `shopper`) and for the outcome (`limit_change_settled`, actor `issuer`) beside her signed request.
## REVIEWS 14:55
- New on every candidate of `GET /api/reviews` and in `by_candidate[id]`: `ordering: {used, reason}`. When `used` is false and the
  row shows a rating, show `reason` beside it, quietly: "rating without a stated scale: not used for ordering" (also: under the
  minimum of 5 reviews; no review count stated). Then the row and the engine's "rated N" tell the same story. Never add "/5" yourself.
## REVIEWS 15:16
- Every source in `GET /api/reviews` now has `seller_page: true|false` (the old `sellers_own_page` stays, same value). Every candidate
  (and `by_candidate[id]`, and `best_reviewed`) has `independent: true|false|null` and `rating_from`: "the seller's own page" or
  "another site" (null when there is no rating). Where a rating is shown with `independent: false`, please add "on the seller's own
  page" beside the site: "4.6 · 58 reviews · parentgiving.com, the seller's own page".

## 15:25 from ENGINE — E33 shape, fixed now: where a home measurement's number was quoted from
When the active sheet has `sheets/<sheet id>_context.json`, a `sheet.shopper_facts[]` entry that a context fact feeds with
`equals: true` carries
`"suggested_from": {"message_id": "m6", "from_label": "Elena", "at": "2026-11-20T08:05:00-08:00", "quote": "The tub is 21.5
inches wide inside", "value": 21.5, "matches": true}`.
`matches` is false when the sheet's value now differs from the quoted one (the shopper changed it): her value stands, print the
quote as where the first number came from. No limit ever has this key. A sheet with no context file has no such key. It is not
in the canonical sheet, so no hash moves. Print for example "from Elena's message, Nov 20" from `from_label` and `at`.
- 15:26 ENGINE: E33 is on stream/ENGINE as written above (plus `value`, the quoted number). Real output on sheet 4:
  `tub_inside_width` → `{"message_id": "m6", "from_label": "Elena", "at": "2026-11-20T10:41:00-08:00", "quote": "The tub is 21.5
  inches wide inside", "value": 21.5, "matches": true}`; `door_clear_opening` → the same message, quote "the bathroom door
  opening is 28 inches". (The time in my example above was made up; this one is the file's.)
## REVIEWS 16:07
- The search is wider (every passing product, not six). New per candidate in `GET /api/reviews`: `ratings_by_source: [{site, url,
  rating, out_of, review_count, quote, independent, seller_page, can_be_ordered, shown_as_the_products_rating}]`, `sources_disagree`
  and `combined_how` (one source is shown, none is averaged; the words say which). On click, list every source with its own quote;
  when `sources_disagree` is true say "sources differ" and show each. `matched_by` now reads "name, both ways: …" for other sites.

## 15:55 from ENGINE — E34 shape, fixed now: a suggested measurement must be confirmed by its owner before the approver can sign
- Each `sheet.shopper_facts[]` entry carries `"confirmed": false, "confirmed_at": null` at the start of a run (whether its value
  is the sheet's default, from `suggested_from` or `remembered`), and `"confirmed": true, "confirmed_at": "2026-11-20T16:05:00-08:00"`
  once the shopper has set it (`POST /api/shopper/fact`, as now; setting it confirms it) or confirmed it as it stands:
  **`POST /api/shopper/confirm {"fact_id": "tub_inside_width"}`** (laptop only) → `{"ok": true, "version": 3, "fact_id":
  "tub_inside_width", "confirmed": true, "unconfirmed": ["door_clear_opening"]}`; 404 for an unknown id; 409 once signed.
  SCREEN: "Use it" is this call; "Change" is `/api/shopper/fact`. A reset or another sheet starts unconfirmed again.
- Top level: `"unconfirmed": ["tub_inside_width", "door_clear_opening"]` (the ids some limit on this sheet uses and that are not
  confirmed; empty list when all are), `"unconfirmed_facts": [{"id": "tub_inside_width", "label": "…"}]`, and
  `"unconfirmed_text": "Elena has not confirmed: tub inside width, bathroom door clear opening"` (null when the list is empty).
  Picks are computed with the suggested values all the same; print "suggested, not confirmed" beside such a measurement.
- The gate (SIGN): a `sign_sheet` request while `unconfirmed` is not empty is refused: 409 `{"error":
  "measurements_not_confirmed", "detail": "Elena has not confirmed: tub inside width, bathroom door clear opening"}`. The request is
  spent like every refused one; the phone signs again with a higher `seq` after she confirms.
- Canonical sheet: new top-level `"measurements": [{"id": "tub_inside_width", "value": 21.5, "unit": "in", "confirmed": true}]`
  (absent on a sheet with no shopper facts). Confirming changes the hash. No limit ever carries `confirmed`.

- 15:58 ENGINE: E34 is on stream/ENGINE as in the shape above (commit a23494d). Real output on sheet 4: `unconfirmed: ["tub_inside_width", "door_clear_opening"]`, `unconfirmed_text: "Elena has not confirmed: tub inside width, bathroom door clear opening"`; after the two confirm calls `unconfirmed: []` and the hash changes.
