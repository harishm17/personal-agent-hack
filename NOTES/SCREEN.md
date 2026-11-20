
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
