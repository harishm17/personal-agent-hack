# Review of everything, 15:00

Written 15:00 to 15:20 from main at `818ba31` and GET requests to the live instance on 8800 (sheet 4,
unsigned, no phone enrolled, no identity inquiry). Pages were rendered with headless Chrome for `/seal/`,
`/talk/`, `/graph/` and `/phone/`; `/` and `/trail/` did not finish rendering in that run, so their lines
below come from `/api/state`, `/api/trail/left`, `/api/tools` and the page scripts. Not run: signing,
carts, the phone, sheet 3 on screen, replay mode. Nothing was written to the live instance.

## Top findings, act on these first

1. **The demo's spine (the approver) is the least finished part of the run of show.** DEMO.md is still the
   14:15 version: five of its nine beats are about reading, memory and the guard; the refused change on the
   laptop and "change one value and the check fails" are not in it at all (I19 is open). The identity gate
   is on by default (`signoff/sign/api.py:344`), so "Sign, tap twice" at 1:55 is refused unless an inquiry
   was approved first, and the 16:50 checklist does not mention it. `/seal/`'s four refused attempts (K6)
   are on `stream/TALK` (15:04), not on main. Rewrite the three minutes around four moments: laptop
   refused, phone changes the limit and the pick moves, two taps and carts, one value changed and the
   signature fails. Section 7 has the order.

2. **The invented timeline contradicts itself on screen.** `sheets/sheet4_context.json`: "Rosa's hip
   replacement is scheduled for Tuesday, November 24", order dated 2026-11-20. Saved conversations in
   `data/talk/threads/sheet4/`: "had a hip replacement last week" (`9b79a4f63b5c`), "had her hip replaced
   last week" (`f9faad4b5aed`), "came home from a hip operation on Monday" (`cbd3c7f37f4f`), "just had hip
   surgery" (`98b830ce0828`, `1553b09d0333`); every model draft says "recently had hip surgery". The
   guard row and `/talk/` show those drafts. Section 4 lists the rest.

3. **Six sponsor sentences in DEMO.md do not match the live instance** (Senso "by version", Persona,
   Firedrill "ran the drill again", Amplitude, Airbyte's row count, and "the limit never goes in").
   Corrected wording is in section 2.

4. **SUBMISSION.md describes a different product** (Priya, Marco the plumber, four stores). Replacement
   text for every field is in section 3. README.md is still the empty template.

5. **Three added pieces are not on the live instance or do nothing there.** No code on main reads
   `sheets/sheet4_context.json` (the event graph is on `stream/GRAPH` only; `/api/graph/explore` has ten
   stages and no event). "Best reviewed" has nothing to order by for two of the three items
   (`/api/reviews?line_id=L1` and `L5`: "no passing product has a quoted rating out of five with at least
   5 reviews"); for the walker the winning rating is "on one site: parentgiving.com (the seller's own
   page)". Sheet 4 has no preference. None of the three belongs in the three minutes.

## 1. Coherence

**Today it is three stories sharing a screen:** (a) an agent that will not buy what it cannot quote,
(b) an approver whose signature is the only thing that creates a cart, (c) a personal agent with memory, a
graph, context messages and a privacy guard. (a) and (b) are one story when told in the right order: (a)
is the evidence that (b) is worth signing. (c) is a second product; its true parts are small on this run
(one remembered measurement, six Cognee datasets, one clean guarded message).

**The one story, as a judge would repeat it:**
"The person who knows what is safe writes the order and holds the only key; the shopper and the agent
cannot change a limit or create a cart. The agent reads real store pages and keeps a figure only when code
finds the store's exact words, so a product that does not state it is not bought. She signs the limits,
the quotes and the picks from her phone, and if one value is changed afterwards the signature no longer
checks."

The sentence for the builder's doubt: a shopping agent with criteria decides for you; this one cannot
decide. It prepares a decision that somebody else owns, and the proof of that is on the signature page,
not in the table of criteria. Lead with the refusal and end on the failed check.

| Piece | Verdict | Reason |
|---|---|---|
| Quote check, code compares, "unclear means not bought" | KEEP IN DEMO (25 s) | The evidence she signs; the grab bar screen reads on its own |
| Laptop's change to a limit refused | KEEP IN DEMO, first | Shows the split of authority in five seconds; currently not in DEMO.md |
| Phone: limit change, pick moves, sign, carts | KEEP IN DEMO | The product |
| `/seal/`: what the signature covers, change one thing | KEEP IN DEMO, last | "7 of 23 rows" against "23 of 23 rows" is the difference from a signed cart |
| K6, "try to get a cart without her" | KEEP IN DEMO if on main and seen by 15:20, else QUESTIONS | Real refusals from the real routes; not merged at 15:05 |
| Guard on what is shared with stores' agents | KEEP IN DEMO as one 10 s step on the Trail, one thread only | Agent to agent with a visible rule is rare; `/talk/` itself shows the false positives and the wrong dates |
| "What left and what never did" matrix | KEEP FOR QUESTIONS | Honest and good, but half its cells say "not recorded" and it shows limits sent to Senso and SingleStore; it needs a minute to read |
| Memory with owners | KEEP FOR QUESTIONS | On this run the shelf holds one measurement (the tub; the door is not there) and 18 store answers; no strike exists; 47 of 96 rows are "not proved" |
| Knowledge graph on Cognee | KEEP FOR QUESTIONS, hide the tab | Real (6 datasets, 1 write refused) but a second picture of the same run |
| Graph view that grows | HIDE | The Trail replay already is the motion; two animated explanations read as two products |
| Web reviews (Exa) | HIDE | Nothing qualifies for two of three items; a seller's own page for the third |
| Shopper-chosen ordering | KEEP FOR QUESTIONS | One true line ("the rules are hers, the taste is the shopper's, and the ordering is under the signature"); on stage it moves the walker from $44.71 to $119.99 on a seller's rating |
| Preferences beside requirements | KEEP FOR QUESTIONS | Only sheet 3's notebook has one; the lead has none |
| Surgery as an event with invented messages | HIDE | Not read by code on main; contradicts the saved conversations; under "limits are prescribed" it feeds only a date and two measurements the sheet already holds |
| Teacher's list (sheet 3) | KEEP IN DEMO only if the spine fits in 2:30, else QUESTIONS | "Same engine" is worth 15 s, less than the failed check |

**Does anything added weaken the core?**
- Ordering by reviews: it does not break "buys nothing it cannot quote" (a rating also needs a quote and
  never changes what passes), but it changes what the demo is about. "Cheapest that meets the order" is a
  rule a therapist can audit; "best reviewed" brings back the shopping agent. Keep it off the stage.
- Context messages: they do weaken "limits are prescribed". Message m6 "About 280 lb" followed by m7
  "Then everything she puts her weight on must be rated for at least 300 lb" shows the limit following
  from context in the therapist's own words, while the file's note says "No fact here feeds a limit".
- A preference beside a requirement: harmless in code (it never changes what passes), invisible on the
  lead sheet.

**Contradictions in words, names, numbers or principle (both sides quoted):**
| A | B |
|---|---|
| CONTRACT.md Amendment 12:10 title: "the agent derives the limits"; live `state.order`: `"limits_derived": 6`; OPEN.md E3: "derived limits per sheet" | Commit `818ba31`: "Limits are prescribed, never derived from context"; OPEN.md H8: "the limits are prescribed, never derived" |
| OPEN.md H7: "280 lb is why 300 lb" | OPEN.md H8: "the event context feeds the date, who is at the house and the measurements, and no limit" |
| DEMO.md 0:50: "The therapist's limit and the family's measurements never go in." | `/api/memory/context`: "read the limits from the written order", 2 calls, `given: ["limit","order","person"]`; the page-reading calls are listed as `given: ["home_measurement","limit","product","store_text"]` |
| `sheet4_context.json` classes: `"home": "never leaves"`, `"person": "never leaves"` | `/api/trail/left`: home measurement `sent` to SingleStore (21) and to the embedding model (3); person `found` in SingleStore (21) and Senso (1) |
| DEMO.md: "It remembers only what a record proves" | `/api/memory` counts: `"proved": 49, "not_proved": 47` (the rule line says those are never recalled, but the number is on the page) |
| DEMO.md hard questions: memory holds "what she struck and why" | `/api/state` memory: `"strikes": []`; the approver's shelf has 0 items |
| DEMO.md Senso: "by version"; OPEN.md G15: "ok" | `/api/senso/checks`: `"version_id": null` on all seven rows |
| DEMO.md Firedrill: "we changed it and ran the drill again" | `/api/tools`: "Re-run after the fix with every criterion met: no"; latest score 70.5, threshold 75 |
| DEMO.md opening: "shops three real stores" | SUBMISSION.md: "searches four real stores" |
| `/seal/`: "checks the real signature, without trusting our server" | `web/seal/seal.js:164`: the text, the signature and the public key all come from `GET /api/seal/proof` on our server |
| Memory rows of kind `purchase`: "The approver signed the order: $114.69, 3 carts." | Everywhere else: "Nothing is checked out" |
| `/api/tools` Airbyte: "311 rows delivered" | `/api/airbyte/status` jobs: 132 + 3 + 12 = 147 rows, for `sheet1` |

## 2. True claims

Evidence is the live route unless a file is named. Corrected wording is ready to paste.

### DEMO.md
| Claim | Verdict | Evidence | Corrected wording |
|---|---|---|---|
| "shops three real stores to that written order" | TRUE with a caveat | sheet 4 stores: carex.com, vivehealth.com, parentgiving.com. The pages were fetched at 11:11 for sheet 1 (`"data_from": "sheet1"`), read once at 13:38 | keep; if asked: "fetched this morning, read once; the carts are made live" |
| "buys nothing until the therapist signs" | TRUE (unsigned state) | `state.seal.text`: "Not signed. No cart exists at any store." | keep |
| "Eighteen cheaper grab bars were rejected, each for a reason" | TRUE in count, loose in noun | L5: 18 rows cheaper than the $27.99 pick: 15 outside, 2 unclear, 1 not stated. They are options (sizes, finishes) of about seven products | "Eighteen cheaper options were turned down, each with its reason." |
| "One states 75 pounds. Her order says 300." | TRUE | Carex Chrome Ultra Grip Bath Handle: "weight capacity: 75 >= 300 is false" | keep |
| "sold as 18 and 36 inch on a page that describes neither" | TRUE | Vive Textured Grab Bars: "option says 18 in; the page describes 12, 16 and 24 in" | keep |
| "This is everything the model gets: one page of the store's own text." | TRUE for the page-reading call | `signoff/extract/reader.py:97`: figure meanings, units and the page text | "This is everything the reading model gets: one store page and the names of the figures." |
| "The therapist's limit and the family's measurements never go in." | FALSE as a general sentence | a model reads the limits from the order; limits go to Senso (25) and SingleStore (21) | "The limit and the house's measurements go round the reading model; code compares them, and no store ever sees them." |
| "the guard stops her limit, the tub's width and her name" | TRUE of one thread only | `cbd3c7f37f4f` turn 1: struck "My mother", "280 lbs", "hip surgery", "300 lbs", "21.5 inches", "therapist", "Dana" | "The guard struck her mother's weight, the surgery, the therapist's limit and the tub's width before the store's agent saw the message." |
| "drag the limit past 350 ... The pick moves to another store, and that store says opened bath seats cannot be returned." | TRUE (computed, not run) | above 350 only Carex Universal Bath Seat without Back (400 lb, 21 in) passes; carex.com answer: "Opened bath seats cannot be returned" | keep; the first step past 350 is 375 |
| "'Carts created' and the two links" | TRUE only after the slider beat | before it the three picks are at three stores (3 carts, $114.69); after it carex.com holds two (2 carts, $119.81) | say the number on the screen |
| "She signed the rules, the quotes and the picks, not just a total." | TRUE | `/seal/`: "Dana signs: 6 limits · 8 quotes · 3 picks"; "This signature covers 23 of 23 rows" | keep |
| "It remembers only what a record proves, and each memory has an owner." | TRUE for what is recalled | 49 proved rows; 47 not proved and "never recalled" | "It recalls only what a record backs, and each memory has an owner." |
| "Next time the house is already measured." | HALF | shelf holds the tub (21.5 in, receipt at 14:17); the door has no memory | drop, or "the tub is already measured" |
| "This children's headphone states 95 decibels; this brand states none." | UNVERIFIED on screen | `data/figures/sheet3/` holds "Output: 85 / 95 dB (switchable)"; sheet 3 not opened on 8800 | check on a copy before saying it |
| Closing: "It read every page" | TRUE as "a model read" | 197 pages by each reader; `hand_checked: false` | "It read every page" is fine; never "we checked" |
| Closing: "The people are invented; the stores, pages and carts are real." | TRUE | sheet 4 `invented_note` | add "and the messages" if any message is shown |
| Hard question: "I read the figures behind this cart myself." | UNVERIFIED | OPEN.md B4 and I3 are open; no record says so | say it only after reading the eight quotes on `/seal/`; else "No person has checked them; the page shows the store's words so she can." |
| Hard question: "it catches five misreads and blocks about twenty-seven right figures" | TRUE as measured | `/api/gate/status`: 5 and 27; "right" means "only the reference reader found", no person judged them | "blocks twenty-seven figures only the first reader found" |
| Hard question: memory holds "what she struck and why" | FALSE on this run | no strike memory exists | "the house's measurements and what each store said, each with its owner" |
| Hard question: "Louck et al. showed that AP2 signs the transaction but not the decision" | UNVERIFIED by me | CONTRACT.md Amendment 12:40 quotes it first-hand | keep the amendment's wording, including "bind the cart to what was displayed" |
| Rehearsal log: "71 signed requests, signed, two real carts" (11:46) | UNVERIFIED | that chain was for an earlier sheet; the current chain has 2 receipts | keep as a log line, do not say it on stage |

### Sponsor sentences
| Tool | DEMO.md says | Verdict | Evidence | Say instead |
|---|---|---|---|---|
| Senso | "Senso checks each sentence of the sheet against her order, by version." | FALSE in two words | 7 sentences (3 items, 4 limits; the tub and door limits are not sent); `version_id: null`; only item sentences have `blocks: true` | "Before she can sign, Senso checks seven sentences of the sheet against her order document; an item that is not on the order blocks the signature." |
| Superlinked SIE | "A second, smaller model reads the same pages. Where the two disagree, the product is unclear." | TRUE | Qwen on SIE read 197 pages; 5 figures read differently; also the guard's span model and the embeddings run on SIE | keep; add "the guard's span model runs there too" |
| Statsig + Amplitude | "We put 'require both readers' behind a gate, measured it, and kept only the part that helped" | TRUE for Statsig; weak for Amplitude | gate read live, "not adopted"; Amplitude: 2 events delivered, 287 tool calls in the local log; the session is named `sheet1-145144-6cd6` on a sheet 4 run | "A Statsig gate switches 'both readers must agree'. We measured it and did not adopt it. Tool calls go to Amplitude with the gate's arm; two were delivered in this run." |
| SingleStore | "The same test runs as one SQL statement; its rows equal the screen's." | TRUE | `/api/tools`: 8 rows for L1, same as the engine's 8 | keep |
| Persona | "The signature waits for an identity inquiry. Sandbox, and the seal says so." | UNVERIFIED; nothing on screen now | `/api/tools` lists Persona under `absent`; the laptop control approves the inquiry through Persona's simulate action, so no person is checked | "The signature waits for a Persona inquiry. It is the sandbox: the inquiry is approved by a test action, and nobody's identity was checked." |
| Firedrill | "It held; its refusal was unhelpful, so we changed it and ran the drill again." | HALF | two campaigns; "Holds the sheet" 99.5; "Names who can make the change" 70.5 under 75; re-run with every criterion met: no | "Firedrill ran two campaigns of attacks we did not write. The sheet held; saying who can make the change scored under its threshold and is still open." |
| Airbyte | "A local Airbyte sync delivered the stores' records; the query gives the same answer on its rows." | TRUE, with a wrong number beside it | last sync 13:09 local, File source to MySQL staging, then our code copies to SingleStore; "311 rows delivered" against 147 in the job list | "An earlier local Airbyte sync moved the store records into staging; the same query on those rows gives the same eight." Fix or remove 311 |
| Cognee | "only if the page says Cognee answered" | TRUE | `/graph/` shows "Answer: Cognee"; 6 datasets, 2 identities, 1 write refused of 15 | "Cognee holds one dataset per owner; a write to the therapist's dataset with the shopper's identity was refused." |
| Exa | none | not a sponsor | used for review search | do not list as a sponsor |

### Lines on the screens
| Line | Where | Verdict | Evidence | Corrected |
|---|---|---|---|---|
| "this browser recomputes the fingerprint and checks the real signature, without trusting our server" | `/seal/` | OVERSTATED | the public key is served by the same route | "…and checks the signature itself. The key to compare is the one on Dana's phone." |
| "A signature over the cart covers 7 of 23 rows" / "This signature covers 23 of 23 rows" | `/seal/` | TRUE | canonical sheet rows | keep |
| "Elena measured · overall width ≤ 28.0 in" | `/seal/` | UNVERIFIED as a record | the door value comes from the sheet file; only the tub has a receipt | "from the house" or leave: the people are invented, and the page says so |
| "8 with the stores' own agents · 31 withheld" | `/talk/` | TRUE | totals: 13 messages, 31 spans stopped, 4 refused; 8 threads | keep |
| no "invented" mark | `/talk/` | MISSING | the top bar of `/talk/` has none; `/seal/` and `/graph/` have "invented people" | add the same mark; the shopper's asks are invented text |
| "identity checked (sandbox)" after the laptop's simulate | phone, seal | MISLEADING | `signoff/sign/persona.py:48`, `:108` | "identity inquiry approved (sandbox test action)" |
| "Graph: the run's records · Answer: Cognee" | `/graph/` | TRUE | `/api/graph/cognee` backend cognee | keep |
| rating "3.9 · 28" on the pick's node | `/api/graph/explore` | INCONSISTENT | `out_of: null`, so the ratings rule rejects it, yet it is drawn | hide a rating the rule does not accept |
| "Rows delivered to SingleStore: 311" | Tools drawer | UNVERIFIED | see Airbyte | 147, or drop |
| Senso `claim`: "Harish's Org's order requires…" | `/api/senso/checks` | check the phone | a real name inside an invented order, if it is drawn | show `sentence`, not `claim` |
| `not_shown: ["sheet1","sheet2","sheet4_context"]` | `/api/sheets` | BUG, harmless | the context file is listed as a sheet | skip files without `lines` |

## 3. SUBMISSION.md, replacement text

Character counts were measured with a script; each is inside its limit. [check] marks what was not seen
by this review.

**Project name** (8 of 140)
Sign-Off

**One-sentence description** (289 of 300)
A shopping agent that works under someone else's signature: a therapist writes what a patient's home needs, the agent keeps a store's figure only as an exact quote that code can find, code compares it with her limits, and carts exist at the real stores only after she signs from her phone.

**Project description** (1,488 of 1500, with the [check] note)
Sign-Off shops real stores to an order that someone else wrote and must sign. Lead example (invented people): Rosa is coming home after a hip replacement. Dana, her occupational therapist, wrote the order: a shower chair, a walker and a grab bar, each to hold at least 300 lb; the chair must fit inside the tub, the walker must pass the bathroom door. Her daughter Elena shops and measures the house. The agent searched three real stores and read 91 product pages. A figure counts only when code finds its exact quote in the store's text; code, not the model, compares it with the limit. A product that does not state a figure is not bought on a guess: of 152 options, 61 pass, 48 fail, 9 are unclear and 34 never state it. Elena's laptop cannot change a limit; the server refuses. Dana can, from her phone, and the pick moves. She signs one fingerprint covering the limits, the measurements, the stores' quotes, the picks, the prices and the ordering; a browser can recompute it, and one changed value fails the check. Only then are carts created at the stores [check: a signed sheet 4 run on main]. Nothing is checked out. When the agent asks a store's own agent about delivery and returns, a guard in code removes limits, measurements, names and health details first, and every outbound payload is in a ledger. A teacher's class supply list runs on the same engine. The people and their messages are invented; the stores, pages, prices and carts are real. No person checked every page.

**Tools and sponsors used**
Senso
SingleStore
Superlinked SIE
Statsig
Amplitude [check: more than two events delivered, or say "two"]
Airbyte
Firedrill
Cognee
Persona [check: only if a sandbox inquiry ran on the submitted build]
Not sponsors: Anthropic Claude (the reference reader), Exa (review search)

**Repository URL**
https://github.com/harishm17/personal-agent-hack [check: public, and it is this repository]

**Demo video URL**
[check: a link that opens while logged out]

**Team**
[the builder fills this in]

**Judge access notes** (909 of 6000)
Everything about the people is invented: Dana, Elena, Rosa, the order and every message. The stores (carex.com, vivehealth.com, parentgiving.com), their product pages, prices and carts are real. Nothing is paid for or checked out; the client never calls a checkout tool.
To look without keys: start the replay (see Setup) and open / (the shopper's screen), /trail/ (each step as a record), /seal/ (what the signature covers; change one value and the check fails) and /phone/ (the approver).
What to try: on the decision screen, "try to change" under a limit: the server refuses it without the approver's key. On /seal/, click any value.
Known limits: store pages were fetched once on the day and read by two models, not by a person. The identity check is Persona's sandbox and checks nobody. The guard on outgoing messages uses a small model to find names and health details and refuses a message when unsure.

**Technical architecture** (1,197 of 1200)
A FastAPI engine with plain JavaScript pages: the shopper's screen, the approver's phone, the trail, the signature page. A reading model with no tools gets one store page and the names of the figures and proposes a figure, unit and quote; code finds the quote in the page and applies one set of number rules to every reader (Claude Sonnet, and Qwen on Superlinked SIE; a disagreement makes the product unclear). Limits are read from the written order with their sentence quoted, compared in code and again in one SingleStore statement. Stores are reached over their own MCP endpoints: search, product details, ask the store's agent, create cart. Records: a decision per candidate and state version, hash-chained receipts, a ledger of every outbound payload. The phone holds an ECDSA P-256 key; each request is signed against the SHA-256 fingerprint of the canonical sheet. Senso checks the sheet's sentences against the order document before signing; a Persona sandbox inquiry gates it; carts are then created for the signed picks only. A Statsig gate switches the two-reader rule. Memory rows carry an owner and the receipt that made them (SingleStore, SIE embeddings, Cognee datasets per owner).

**Setup instructions** (371 of 1200) [check: run these once on a clean clone]
Needs Python 3.12+ and uv.
uv sync
SIGNOFF_MODE=replay SIGNOFF_SHEET=sheet4 uv run uvicorn signoff.app:app --port 8800
Open http://localhost:8800 for the shopper's screen and http://localhost:8800/phone/ for the approver. Replay mode uses the store data saved on the day and says so in the top bar. Live mode needs the keys named in .env.example [check: the file exists].

**Lessons learned** (880 of 1200)
The strict rule was the wrong default. Requiring two readers to agree on every figure caught five misreads and blocked twenty-seven figures that only one reader found; we measured it behind a gate and kept "a disagreement blocks" instead.
"Unclear" had to be its own answer. A page that sells an 18 inch option and describes only 12, 16 and 24 is neither a pass nor a fail, and saying so is more useful than guessing.
A signature over a cart covers very little. Putting the limits, the quotes and the ordering under it is what lets a second person be responsible for a purchase she did not make.
A guard that finds names with a model refuses too much: it took "I" for a person and a store's name for one. Values from the order are caught exactly; free text is not.
We added more than one demo can carry. The parts that survived are the ones that answer "who is allowed to decide".

**Project screenshot**
[check: `/seal/` after a signed run, under 5 MB]

## 4. Consistency of the invented world

| # | Mismatch | Where |
|---|---|---|
| 1 | Surgery in the future (Nov 24) against "last week", "just had", "on Monday" | context file m1, facts; talk threads `9b79a4f63b5c`, `f9faad4b5aed`, `cbd3c7f37f4f`, `98b830ce0828`, `1553b09d0333` |
| 2 | "came home from a hip operation on Monday" against "discharge Rosa ... on Wednesday, December 2" | `cbd3c7f37f4f` purpose; context m4 |
| 3 | DEMO.md opening "A patient comes home after surgery" reads as already home; the order title says "coming home"; the context says not yet operated | DEMO.md; `sheet4_order.txt` line 1 |
| 4 | Elena's measurements: sent to Dana at 10:41 (m6) against "measured_at 14:17" for the tub in memory; the door has no measurement record | context m6; `/api/state` memory |
| 5 | The limit follows the weight in Dana's own message ("About 280 lb" ... "Then everything ... at least 300 lb") against "No fact here feeds a limit" | context m6, m7; context `reading` |
| 6 | Rosa is named in the context file and two shopper asks; the sheet, the order and the matrix's example ("Dana, Elena") do not know her, so on main her name and weight are caught only by the span model (scores 0.73 to 0.90), not as known values | `sheet4.json`; `/api/trail/left` rows |
| 7 | "Mum" in the typed asks, "Mom" in the family chat (m2) | talk purposes; context m2 |
| 8 | The store question says "to a California address"; nothing in the invented world says where the house is | `signoff/store/ask.py:17` |
| 9 | "the two links" (carts) against three picks at three stores before the slider beat | DEMO.md 1:55; `/api/state` |
| 10 | Senso's claim text names "Harish's Org" as the order's owner; the order is Dana's | `/api/senso/checks` `claim` |
| 11 | SUBMISSION.md: Priya, Marco, four stores, toilets | whole file |

Consistent: Dana (occupational therapist), Elena (daughter, shopper), Rosa (Elena's mother), Marcus
(Elena's brother); weekdays (Tuesday November 24, Wednesday December 2, and today, November 20 2026, is a
Friday); need-by 2026-12-02 in the sheet, the order, the context and every store message; 300 lb, 16 in,
21.5 in and 28 in everywhere; order written at 11:00 after Dana's 10:55 "I will send the written order
this morning"; sheet 3's names (Ms. Alvarez, Dev, 24 students, need-by 2026-12-04).

## 5. Overfitting, staging, silent fallbacks

| # | What | Where | Kind |
|---|---|---|---|
| 1 | `ORDER_NAME = {"shower chair": "shower chair or transfer bench"}` | `signoff/sign/senso.py:33` | a rule keyed to one item; move the wording to the sheet line |
| 2 | "to a California address" in every store question | `signoff/store/ask.py:17` | hard-coded region; should come from the sheet |
| 3 | One question about shower chairs and bath seats is each store's answer on returns for every item | `data/store_answers/*.json`, `scope: "store-wide"` | acceptable, but the walker's and grab bar's return terms are not asked for |
| 4 | The shopper's five asks in `/talk/` were typed to provoke the guard ("Please let the store know Mum is 280 pounds…") | `data/talk/threads/sheet4/*.json` `purpose` | staged input, real guard run; say "we typed these to test the guard" if shown |
| 5 | `sheet4_context.json`: messages written so that `equals` checks pass; nothing on main reads it | `sheets/sheet4_context.json` | exists only to look good; hide |
| 6 | The identity gate is passed with a laptop control and then reads "identity checked (sandbox)" | `signoff/sign/api.py:559`, `persona.py:48` | a rehearsal control on the demo path; reword the label |
| 7 | The lead sheet has no fetch of its own (`data_from: sheet1`), and the bar says `live` | `sheets/sheet4.json` | fine if said; "fetched this morning" |
| 8 | The guard's rule is `"source": "default"`, not from the sheet | `/api/talk/threads` `rule` | K2 says "from the sheet"; either is fine, the words should match |
| 9 | Amplitude session and several defaults fall back to `"sheet1"` | `signoff/obs/__init__.py:147`, `:255`; `obs/egress.py:194` | a silent default; the sheet 4 run is recorded as sheet 1 |
| 10 | Optional routers that fail to import are skipped; only `/api/health` says so | `signoff/app.py:60` | silent on the pages; check `/api/health` shows `"skipped": {}` at 16:50 (it does now) |
| 11 | If the engine router is missing, `/api/state` serves a committed fixture | `signoff/app.py:71` | silent fallback; the screen would show `fixture data` only if `mode` says so |
| 12 | The ledger's value search marks page-reading calls as carrying a "limit" and a "home measurement" when the store's page happens to print "300 lb" or "21.5" | `/api/memory/context` | a false alarm that contradicts the Trail's headline; label it "same number in the store's text" |

Not found: any pick forced for one product, any hard-coded pass, any hidden row. The planted page is out
of the live state (`instruction_scan`: 0 found on 91 pages). `degraded` is empty.

## 6. Three questions he cannot answer well today

**Q1. "What does her signature prove? The key lives in a web page, your identity check is a sandbox, and
your own server hands the browser the key it verifies with."**
Best true answer: "It states one thing: the holder of the key that was enrolled with the laptop's one-time
code approved exactly these 23 rows. The server will not move a limit or create a cart without that key;
you can try. It does not establish who she is: Persona runs in its sandbox and the page says so. The
independent check is the fingerprint, which her phone computes from the sheet itself and shows beside the
laptop's."

**Q2. "Did a person check any of these figures? How do you know 350 lb is right?"**
Best true answer: "No person read every page. Each figure is the store's own sentence, found by code at
its place on the page; a second model read the same pages and five disagreements were set to unclear. We
did not measure accuracy against a hand-read set. That is why the approver is shown the quote, not our
reading, and why she, not the agent, is the one who signs." (Then read the eight quotes behind the cart
before 16:30, so that "I read these eight myself" is true.)

**Q3. "You say her limits and health details never leave. Your own matrix shows limits sent to Senso and
SingleStore, and your guard is a model."**
Best true answer: "Never to a store, and never to the model that reads store pages. The limits do go to
the services we chose to hold them, Senso and SingleStore, and one model call reads them from her order;
the ledger lists every payload. Values that are in the order, like 300 lb or the tub's 21.5 inches, are
stopped by exact match. Free text such as a name or a weight is found by a small model, which is why the
guard refuses a message when unsure: 4 of 13 were refused outright, two of them wrongly."

Also likely: "Is anything live?" (pages fetched 11:11 today, read at 13:38; carts created live on
signing), and "What did Statsig and Amplitude decide?" (nothing was adopted; the gate is off).

## 7. Three changes in the remaining 25 minutes

1. **Make the approver the spine, in DEMO.md and on main.** Merge K6 only if its tests pass on main;
   otherwise leave it. Add to the 16:50 checklist: "identity inquiry approved; the phone reads 'needed to
   sign' no longer". New order of beats: 0:00 opening on the order; 0:15 "try to change" on the laptop,
   refused; 0:25 grab bar, 18 cheaper options, 75 lb, unclear; 0:55 Trail, one page into the reading
   model, the limit going round, one guard step; 1:25 phone, limit to 375, pick moves to carex.com; 1:50
   two taps, carts; 2:10 `/seal/`, 23 of 23 rows, change one value, the check fails; 2:35 teacher's list
   or the closing. Drop the memory beat.
2. **Correct the words that are false on screen or in the script** (no new features): Senso "by version";
   Airbyte 311; the Persona label after a simulate action; `/seal/` "without trusting our server";
   "invented people" on `/talk/`; the drawn rating that the rule rejects; show "read from her order"
   where a screen says "derived". Replace SUBMISSION.md with section 3.
3. **Remove the contradiction in the invented world, and narrow the top bar.** Either re-run the three
   shopper asks with wording that fits the context ("is having a hip replacement on the 24th and comes
   home on December 2"; one command each, `signoff.talk.run --sheet sheet4 --store … --text …`) or keep
   the shopper's threads out of every shot. In m7 drop "Then". For the stage and the video, show three
   tabs: Decision, Trail, Signature. Memory, Conversations and the graph stay reachable for questions.
