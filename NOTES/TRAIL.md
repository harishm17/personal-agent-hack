# Notes for TRAIL

## 12:55 from SCREEN: the visual system to match
Link `/screen/style.css` and use its variables and classes; do not copy values. It is the shared system for `/` and `/trail/`.
- **Scale.** Everything is in rem. `html { font-size: clamp(16px, 1.1vw, 22px) }` is set in style.css: 16 px at 1440 wide,
  about 21 px on a 1920 projector, never under 16 px so browser zoom still works. No px sizes except 1 px hairlines.
- **Type.** One family (`var(--f)`), weights 400 and 600 (500 for emphasis inside a line). Display 1.25rem/1.75rem 600, one
  per view. Body 0.875rem/1.25rem. Secondary 0.8125rem. Caption `.cap`, `.small` 0.75rem/1rem. Tabular numerals are on
  for the whole body. `var(--mono)` only for hashes and codes.
- **Colour.** Ground `--bg`, surfaces `--surface`, hairlines `--line`. Text `--t1` / `--t2` / `--t3`. Marks `--dot`,
  `--dot-out`, `--accent` (near-black: the pick, the active thing). Green `--ok` only as a small tick; `--bad` only for
  a refusal or a failed check; `--mark` behind a quoted figure (`<mark>`). `--issuer` / `--shopper` / `--store` only as
  6 px dots (`<i class="od store"></i>`), never as text colour.
- **Spacing and shape.** 8 px grid (0.5rem); cards `.card` (1 px `--line`, radius `--r` = 0.5rem, padding 1rem, gap
  0.75rem); pills `.pill` fully round, 1.25rem tall. No shadows except the side sheet's; no dashed boxes.
- **Text budget.** Labels of five words or fewer on the surface; anything longer behind a click.
- **Top bar** (copy this markup; `.top` is 3rem tall, `--bar`):
  ```html
  <header class="top">
    <span class="brand">Sign-Off</span>
    <nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/" aria-current="page">Trail</a></nav>
    <span class="sheet">{sheet.title}</span><span class="meta">{n} items · invented</span>
    <span class="grow"></span>
    <span class="pill">Not signed</span>   <!-- class "pill signed" and "Signed 11:46" after signing -->
    <span class="total">$279.04</span>
  </header>
  ```
  The Decision screen already links to `/trail/` in its tabs. Title, item count, `invented`, the signed time and the
  total all come from `/api/state` (`sheet.title`, `lines.length`, `sheet.invented`, `seal.signed`, `seal.signed_at`,
  `total_cents`); when `mode` is `fixture` or `replay` add "fixture data" or "replay of cached store data" to `.meta`.
- **Motion.** 200 to 400 ms, `cubic-bezier(.3, .1, .2, 1)`, only for a real change in the data; off for
  `prefers-reduced-motion`, `?motion=0` and automated browsers. `web/screen/motion.js` exports `MOTION`, `EASE`,
  `arrive`, `appear`, `roll`; import it rather than writing new helpers.
- The Decision screen is being redesigned now (products as a list with requirement cells); style.css stays the base.

## 13:58 from MEMORY — the memory routes are stable (shape of a row and of `GET /api/memory`: NOTES/GRAPH.md, 13:58)
- `GET /api/memory/recall` → what a new run of the sheet on the table starts with: `{sheet_id, facts: [{fact_id, value, unit, measured_by, measured_at, used_by: [limit ids], age: {seconds, text}, memory_id, source, text}],
  strikes: [{line_id, product_key, title, reason, by: "issuer", by_name, at, age, memory_id, source, text}], store_answers: [{store, key, line_id, asked_at, age, memory_id, source, text}],
  purchases: [{signed_at, total_cents, carts, sheet_hash, ...}], counts: {recalled, of}, read_from, error}`.
- `GET /api/memory/recall?line_id=L5` → `{line_id, need, recalled: [{kind, owner, why, text, age, memory_id, source, ...}], counts: {recalled, of}}`: what bears on one item and why.
- What the engine applied is already in `/api/state` → `memory` and on the fact (`remembered`, `measured_by`, `measured_at`) and the strike (`from_memory: true`). A short line is enough: "remembered · Elena · 13:57", "struck before · <reason>", "asked 2 h 43 min ago".
- 14:05 from MEMORY: `GET /api/memory/context` → `{model_calls, calls_given_memory, calls_given_no_memory, by_call: [{recipient, purpose, calls, bytes_per_call, given: [classes],
  payloads_containing_a_home_value, calls_given_memory}], sheets_counted}`, counted from the ledger. One line is enough: "347 model calls · 0 given memory".
  `GET /api/memory/recall?line_id=` now also has `by_meaning: {query, recalled, of, ranked: [{score, owner, kind, text, memory_id, source}], error}`.

## 14:08 from MEMORY — the shelf: `GET /api/memory` → `shelf` is stable (on 8007 now; on main after the next merge)
```json
"shelf": [
 {"slot": "shopper",  "owner": "shopper",    "name": "Elena", "items": [<card>]},
 {"slot": "approver", "owner": "issuer",     "name": "Dana",  "items": [<card>]},
 {"slot": "stores",   "owner": "each store", "name": null,    "items": [<card>]},   // card.owner is the store's domain
 {"slot": "bought",   "owner": "issuer",     "name": "Dana",  "items": [<card>]}]
```
A `<card>`: `{memory_id, owner, kind, text, source, at, age: {seconds, text}}` plus, by kind: `home_measurement` → `fact_id, value, unit`; `strike` → `line_id, product_key, title, reason`;
`store_answer` → `key` (`delivery`, `returns`, or `<figure>:<product id>`), `line_id`; `purchase` → `total_cents, carts`.
- `text` is one plain sentence ("Elena measured the tub inside width: 22.0 in."); `source` is `{type: "receipt", chain, n, hash, file, at}` or `{type: "file", file, index, at}`; `age.text` is "2 h 51 min".
- The shelf holds what a new run of the sheet on the table would recall (newest measurement per fact, strikes not undone, this order's stores, this sheet's signed orders). Everything ever kept, by owner, is in `owners[].rows` (each row also has `age` and `on_shelf`).
- Which cards were recalled for one item: `GET /api/memory/recall?line_id=L1` → `recalled: [{memory_id, kind, owner, why, text, age, ...}]`; match `memory_id` to the shelf's cards. `why` is short ("bounds \"fits inside the tub\" on this item").
- "recalled from memory" on a measurement: the engine marks the fact in `/api/state` (`remembered: true, measured_by, measured_at`) and a strike with `from_memory: true`.
- One thing to draw truthfully: a card exists from the moment its receipt exists (a measurement when Elena sets it, a strike when Dana's signed request is accepted), not only at the signature. Only the "bought" card appears on signing. On 8007 after one run: shopper 1, approver 1, stores 9, bought 1.
## TALK 14:10 — the guard row: `GET /api/talk/threads` → `messages` (stable; on `stream/TALK`, served on port 8008 now)
`messages` is a flat list, oldest first, one entry per outbound message of the active sheet (`?sheet=sheet4` for another).
Every string that came from a store is untrusted text: escape it. Shape of one entry (real, 14:02 today):
```
{"id": "cbd3c7f37f4f:1", "thread": "cbd3c7f37f4f", "n": 1,        n: 1 first message, 2 the one follow-up
 "origin": "shopper",                                             "shopper" (the shopper's own words) | "agent" (its own question about a pick)
 "store": "parentgiving.com",
 "product": {"id": "gid://shopify/Product/8045699104933", "title": "Deluxe Aluminum Bath Bench by Drive"},   may be null
 "at": "2026-11-20T14:02:10-08:00",
 "purpose": "Mum weighs 280 pounds and came home from a hip operation on Monday. Tell the store that, …",
 "draft": "My mother, who weighs 280 lbs and recently had hip surgery, needs a Deluxe Aluminum Bath Bench by Drive that supports 300 lbs …",
 "removed": [{"text": "My mother", "class": "person", "mark": "a person", "rule": "a person is sealed for a store (family member)",
              "by": "span model", "start": 0, "end": 9}, …],      start/end are offsets in `draft`; by: "sheet value" | "span model"
 "decision": "rewritten",                                         "sent" (clean as written) | "rewritten" (cut, then sent) | "refused" (not sent)
 "why": null,                                                     set when refused
 "sent": "Please arrange for expedited shipping of the Deluxe Aluminum Bath Bench by Drive to ensure it arrives by December 2, 2026. Could you also confirm if an opened item can be returned?",   null when refused
 "left": [{"class": "product", "mark": "product name", "text": "Deluxe Aluminum Bath Bench by Drive"},
          {"class": "need_by", "mark": "need-by date", "text": "December 2, 2026"}],   the permitted facts `sent` carries; [] when refused
 "reply": {"text": "Nothing has been arranged, and the store’s information does not specify expedited shipping …",
           "at": "2026-11-20T14:02:10-08:00",
           "answers": [{"start": 0, "end": 132, "quote": "…", "question": "…"}, …]}}   offsets in reply.text; null when nothing was sent
```
- `class` is one of limit, home_measurement, person, health, money, address (and need_by, delivery_region, product if a
  sheet's `sharing` seals those). `mark` is the two-word label for a chip; the same labels are in the top-level `marks`.
- The top level also has `rule` (`{recipient, may, sealed, source}`) and `threads` (the same data grouped per conversation).
- For the lead row use `id: "cbd3c7f37f4f:1"`: 7 removed, sent, a real reply. `cbd3c7f37f4f:2` is its follow-up, refused.
  The agent's own questions (`origin: "agent"`, 6 messages, 3 stores) have `removed: []`: nothing was stopped, by design.
- Two earlier asks (`f9faad4b5aed:1`, `1553b09d0333:1`) were refused and sent nothing; they are real and stay in the list.

## TALK 14:15 — one added field in `messages`, nothing changed
- `purpose_removed`: what the guard finds in the shopper's own words, same span shape as `removed`, offsets in `purpose`;
  null for the agent's own questions, for a follow-up and for threads saved before 14:12. Optional to draw.
- A second sent example for the guard row: `98b830ce0828:1` (vivehealth.com, grab bars; six removed, sent, real reply) and
  its follow-up `98b830ce0828:2` (three removed, sent, real reply). `cbd3c7f37f4f:1` stays valid.
## REVIEWS 14:20
- A new step for the run, "Reviews read": `GET /api/reviews/log` → `{step: "Reviews read", recipient: "exa.ai", searches: [...],
  sent_only_product_titles: true|false, sealed_values_found_in_any_search: []}`. Each search:
  `{step, at, service, query, sent: {query, numResults, contents}, sent_is_only_the_product_title_and_review, ledger: {n, at, recipient,
  kind, purpose, bytes, payload_sha256, fact_classes, sealed_found_in_payload}, sent_matches_the_ledger_hash, key_used, pages_returned,
  pages_read, quotes_kept, dropped, found, note, cost_dollars, serves: {line_id, candidate_ids} | null}`.
- One plain sentence per search is enough: "Asked exa.ai for 'Carex Folding Walker review': 4 pages, 8 quotes kept, 2 dropped."
  What left: the product's title and the word "review". `sent` is the whole body; `sent_matches_the_ledger_hash` says code hashed
  that body again and got the ledger row's SHA-256. No limit, no measurement, no name: `ledger.sealed_found_in_payload` is `[]`.
- The reader model was sent the product's title and the returned page text (ledger rows with purpose "propose review quotes from one
  web page", recipient `sie:Qwen/Qwen3.8-27B-FP8`). Nothing of the sheet is in those either.
- Know this: the ledger file is per checkout. The 14 searches were made from the REVIEWS checkout, so their rows are in the cache
  entries (`data/reviews/*.json`, field `ledger`) and in this route, not in main's `/api/egress`. A search made on main adds a row there.
- Reviews are after the pick and beside it: they change no status and no pick. Please do not draw them as a gate.

## TALK 14:50 — one top bar on every page (the integrator, 14:46)
- Please print these five tabs, with `aria-current="page"` on your own: `<nav class="tabs" aria-label="Views"><a href="/">Decision</a><a href="/trail/">Trail</a><a href="/graph/">Memory</a><a href="/talk/">Conversations</a><a href="/seal/">Signature</a></nav>`
  `/seal/` is the Signature page (`web/seal/`, on `stream/TALK`).
