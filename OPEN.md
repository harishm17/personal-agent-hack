# Open items

The builder's rule (13:15): "ensure we implement all carefully; don't skip stuff as much as possible; we forget
about it and don't come back to it sometimes." Every instruction given to a stream is a line here until it
is on main and seen working, or is cut on purpose with the reason written down. The integrator reconciles
this file at every merge. A stream closes an item by writing `DONE <id>: <proof>` in NOTES/INTEGRATOR.md, or
`WONTDO <id>: <reason>`; nothing is dropped silently. Cut-off for anything not on main and rehearsed: 14:30.

Status: `open`, `main` (merged, not yet seen working by the integrator), `ok` (seen working), `cut` (with reason).

## ENGINE
| id | item | status |
|---|---|---|
| E1 | `==` as a real comparison; an unknown op or pick rule is an error | ok |
| E2 | units gpf and gpm | ok |
| E3 | order document and derived limits per sheet (`order_doc`) | ok |
| E4 | store replies and the instruction scan per sheet; one path rule, no hard-coded `sheet1` | ok |
| E5 | pick rule by id (`cheapest` for sheet 2; sheet 1 unchanged) | ok |
| E6 | names, not pronouns, in the chat | ok |
| E7 | rule 1: every stated value is tested; new status `unclear`; a number with no unit is `unclear` | ok |
| E8 | rule 2: every option on sale is its own candidate (needs S1) | ok |
| E9 | rule 3: a limit is compared as the order's sentence is written (at least, at most, equals, fits) | ok |
| E10 | figure meanings live in the sheet; no built-in glossary; the prompt asks what the page states, not an "exact measure" | ok |
| E11 | planted page out of the live state by default; its wording out of the scan prompt and pattern; `instruction_scan` key | ok |
| E12 | readers: `disagreements`, `extra`, `picks_changed`; agreement reported after the rules, unclear ones counted | ok |
| E13 | sheet 2 read end to end; report per item (candidates, inside, outside, unclear, not stated, pick) | ok |
| E14 | sheet 1 re-read under the three rules; before and after per item | ok |
| E15 | `image_url` passed through on `product` (needs S4) | ok |
| E16 | `obs.egress` called for every model call (reader, SIE, chat) | ok |
| E17 | fixture fallback in `extract/run.py` removed or shown in `degraded` | ok |
| E18 | sheet 1's figure meanings, in the order's words, sent to the integrator for `sheets/sheet1.json` | ok |
| E21 | units declared in the sheet (`units`: name and its spellings), so a new sheet needs no code: dB, mph, mg come from sheets/sheet3.json; the built-in table stays only as a default | ok |
| E22 | sheet 3 (the teacher's list, now the lead example) read end to end once S16 exists; `several: "largest"` on the headphone limit; report per item | ok |
| E23 | a line's optional `quantity` carried into the canonical pick, the cart and the total (general; sheet 3 uses 24) | ok |
| E24 | `data_from`: a sheet may name the sheet whose fetched data it uses (one path rule); sheet 4 read end to end from sheet 1's data with its own order document; report per item | ok |
| E25 | `POST /api/admin/use-sheet` (laptop only): switch the running sheet, reset the run, start a new receipt chain; `GET /api/sheets` lists them | ok |
| E26 | an option row must not be given a statement about a different option (Vive Textured Grab Bars: the 18 Inch and 36 Inch options read as 12 in); such a row is `unclear`; all option rows on sheets 4 and 3 re-checked | open |
| E27 | a figure counts only when two independent readers report the same value (reference and Qwen on SIE); otherwise `unclear` ("readers disagree", "only one reader found it"); a switch the gate drives; effect on sheets 4 and 3 reported before it is the default; cut at 14:05 if not feasible | open |
| E28 | two hooks for memory: on reset and use-sheet the engine applies what `signoff.memory.recall(sheet)` returns (home measurements marked remembered; earlier strikes marked from memory, still under the hash); nothing else in the pick path changes | open |
| E29 | the shopper may choose any candidate that passes (`POST /api/shopper/choose`); `picked_by` in the state and the canonical sheet; refused for anything not inside; WONTDO if over fifteen minutes | open |
| E30 | the shopper chooses the ordering among the products that pass: `cheapest`, `best_reviewed`, `best_value` (`POST /api/shopper/pick_rule {id}`); each rule is one sort key, stated on the line (`why.rule`, how many had a quoted rating); ratings come from the reviews cache only; the hash already covers the rule (the builder, 14:24) | open |
| E31 | an order's rule may be a preference, not a requirement: a line's optional `preferences` (same shape as a limit), checked with the same function on figures already read; never changes whether a product passes; among those that pass, more preferences met come first; each candidate carries `preferences: [{id, label, status}]`; under the hash (the builder, 14:24) | open |
| E32 | a fourth ordering, `most_popular`: the most reviews counted, from the same quoted review counts (the builder, 14:31) | open |
| E19 | receipts for every state change; `GET /api/receipts/verify` | ok |
| E20 | seal race, hash covers pick rule, delivery quotes, quantity, currency, variant; scope; `degraded` | ok |

## STORE
| id | item | status |
|---|---|---|
| S1 | both pools carry every in-stock option (`options`) | ok |
| S2 | brand list and per-type word lists removed; products kept by the store's own category; questions built from the sheet line | ok |
| S3 | store agents asked about delivery and returns only | ok |
| S4 | `image_url` on every product | ok |
| S5 | outbound ledger counts from the saved log, for the active sheet | ok |
| S6 | `parse_reply`: a reply that says the store does not say is "unclear" | ok |
| S7 | `create_carts` with `timeout_s` and `tries`; one real cart test at each sheet 2 store that has a pick | ok |
| S8 | SQL for the active sheet agrees with the engine (==, units, unclear) | ok |
| S9 | `/api/gate/status`: decision "switched back" with the evidence fields | ok |
| S10 | a local log of tool-call events with timings for the trail (`signoff.obs.recent()`) | ok |
| S11 | Amplitude: do home measurements, limits or the order's text ride along in events? Answer and set the content mode | ok |
| S12 | replay mode for sheet 2 | ok |
| S16 | sheet 3 pool and store answers fetched once into data/sheet3/ (the teacher's list: eleven stores, four lines), with options and images; counts per store and line in NOTES | ok |
| S17 | tables, SQL, ledger, replay and carts follow sheet 4 through `data_from`; `create_carts` returns the cart's `lines` so SIGN's line comparison (G6) can run | ok |
| S18 | `GET /api/tools`: one real number per tool used in this run, each with its source | open |
| S13 | Amplitude: the gate's variant attached to the session from its start (`experiments` is null now); both arms run once; delivered counts checked (only 2 events were delivered in the 13:25 run) | open |
| S14 | the gate's verdict re-run after the three reading rules; it says "kept" or "switched back" from the numbers, with the evidence; no line claims Amplitude decided it | open |
| S15 | `/api/sql/passing-box?source=airbyte` runs the same statement on the rows Airbyte delivered (`airbyte_pool`), only if under 20 minutes; otherwise WONTDO and the claim is "delivered beforehand" | open |

## SIGN
| id | item | status |
|---|---|---|
| G1 | the sign tap answers within about 8 s; Senso runs in the background, never inside the tap | ok |
| G2 | enrolment needs the laptop's one-time code | ok |
| G3 | one answer for an unsigned request | ok |
| G4 | display binding: the phone hashes `/api/sheet/canonical` itself and renders the review from it | ok |
| G5 | carts created for exactly the engine's signed picks | ok |
| G6 | cart lines compared with the signed picks; "store total differs" shown with both values | ok |
| G7 | Persona as a gate: signature refused until the inquiry is approved; decline and approve shown | ok |
| G8 | review-and-sign phone: no sheet 1 assumptions, the decision screen's tokens, sentence case | ok |
| G9 | Senso documents and sentences for sheet 2 | ok |
| G10 | receipts for every signed request, enrolment, Persona and Senso result | ok |
| G11 | `obs.egress` for every Senso, Persona and Firedrill request | ok |
| G12 | the Relay result on the signature record (`relay`) | ok |
| G13 | screenshots of every phone state at 390 x 844, looked at | ok |
| G14 | Firedrill: retry until 14:00; if it runs, a campaign and what it found; if not, Firedrill is not claimed | open |
| G17 | Senso documents and sentences for sheet 3 (`sheets/sheet3_order.txt`); one rehearsal of the phone on sheet 3 in replay mode | open |
| G18 | Senso's order document and sentences for sheet 4; one phone rehearsal on sheet 4 in replay mode with screenshots | open |
| G15 | Senso: resolve and show the `version_id` of the order document beside each verdict (rows carry `content_id` only) | ok |
| G16 | `PERSONA_REQUIRED` on by default for the demo sheet once G7 works; Relay's sandbox passes with nobody present: say "sandbox" beside it | ok |
| G22 | the phone names the ordering the shopper chose and lists the order's preferences as preferences; the sheet 3 order check passes with its preference sentence | open |
| G23 | the shopper asks, the approver decides: `POST /api/shopper/ask-change`, `GET /api/asks`, a card on the phone with Accept (her existing signed limit change, linked by `ask_id`) and Decline (signed); an ask changes no limit and no hash; records for the trail (the builder, 15:02: "then why the option in the first place") | open |

## SCREEN
| id | item | status |
|---|---|---|
| C1 | the product-list screen, static pass (order document, cheapest-first rows, why-this-one, signature) | main |
| C2 | the stepper of the run and a drawer per step (from `/api/trail`) | open |
| C3 | motion: rows checked top to bottom; a limit change re-checks cells and moves the highlight; signing | open |
| C4 | statuses outside, unclear, not stated visibly different; option rows; images | main |
| C5 | scale and zoom: 150% and 1920 x 1080 | open |
| C6 | signature block: QR and one line; receipts as ticks with a count; signed state with "self-declared" or "identity checked (sandbox)" | open |
| C7 | the unsigned-change control answering in a toast; tabs Decision and Trail; reader chip "switched back" | open |
| C9 | a quiet sheet switcher in the top bar (from `GET /api/sheets`), laptop only | main |
| C10 | evidence shows the shortest statement that carries the value for this option, with the reason it was matched; the "Method" line replaced by what guards the right number (two readers agree, the number sits with its label, every stated value passes), only as far as it is true in the state | open |
| C11 | a passing row can be chosen by the shopper ("choose this one"), shown as chosen by her; only when the route exists | open |
| C12 | the demo director's six fixes (unclear rows say why; the fold line summarises what it folds; plurals; the 404; a warning before switching sheets; "now at <store>" when a pick moves) | open |
| C13 | a "Tools at work" drawer from `GET /api/tools` | open |
| C14 | an ordering control on the decision screen (Cheapest · Best reviewed · Best value) that moves the pick; the pick labelled "Recommended" with its one-line reason; a quiet rating on passing rows; a "preferred" mark on rows that meet a preference (E30, E31, R4) | open |
| C15 | no control on the laptop that can only fail: the "change" link on limits removed; limits read as the approver's, read-only; "Ask Dana" with a value and a note when the route exists, and its state on the limit (waiting, changed, declined) (the builder, 15:02) | open |
| C16 | "Replay the run" on the decision screen: the step bar's control opens an overlay that plays how the agent got here (the graph's embed mode) once and returns to the list; never on page load; hidden when the embed is unavailable (the builder, 15:09) | open |
| C8 | Detail view, dots, rulers, trays and tiles removed | open |

## TRAIL
| id | item | status |
|---|---|---|
| T1 | `GET /api/trail`: real records only, each with `step` and `kind` (evidence, reading, check, approval, action) | ok |
| T2 | `/trail/`: the seven steps as a timeline, events one line each, side sheet with quote and hash | open |
| T4 | context per model call made visible from the ledger: given (one page, figure meanings) and not given (limits, prices, other pages, the order, people); one summary line with real counts | open |
| T5 | the replay at the top of /trail/: real context as cards moving from where it lives into each step and out to the result; a model call's context window; the guard; memory written and recalled; play, step, scrub; on main by 14:45 | open |
| T6 | "What left, and what never did": on `/trail/`, a matrix of the classes of fact the agent holds (rows, from the records and the sharing rule) against every recipient in the outbound ledger (columns); each cell sent · N, stopped · N or never, each clickable to its ledger or guard records; "not recorded" where the ledger cannot tell; a leak shown in red; real totals in one line (the builder, 14:40) | open |
| T3 | the decision screen's visual system; no dots, no arrows | open |

## MEMORY
| id | item | status |
|---|---|---|
| M1 | the memory store: every memory has an owner, a kind, the receipt that created it and a time; written only from real records (the receipt chain), never from model text | open |
| M2 | recall on a new run: the home's measurements, the approver's earlier strikes with their reasons, the stores' answers with their age; `GET /api/memory`, optional `memory` key for the screen | open |
| M3 | recall by meaning for an item (SIE embeddings, SingleStore vector search filtered by owner), shown as "N recalled of M", with what was given to which model call | open |
| M4 | a second run shown working: after a signed run, a reset keeps what was learned and a struck product stays out without anyone striking it again | open |

## TALK (agent to agent, with a guard on what is shared)
| id | item | status |
|---|---|---|
| K1 | the agent composes its own messages to each store's own agent (a model writes them) and may ask one follow-up; real calls, cached | open |
| K2 | the guard, in code: a sharing rule per kind of fact and recipient from the sheet; every outbound message checked for sealed values and for health, person, money and address spans (a small Superlinked model finds them, code decides); blocked spans removed or the message refused; every decision in the outbound ledger | open |
| K3 | a real blocked share: the shopper asks the agent to tell a store something sealed; the draft, what was removed and what was sent are recorded | open |
| K4 | `/talk/`: each store conversation as a thread (sent, withheld, the store agent's reply quoted), in the product's visual system; `GET /api/talk/threads` | open |
| K5 | `/seal/`, the signature shown: who holds what (the key stays on the phone; the agent holds none), what the signature covers (every rule, measurement, store quote, pick, price and the ordering, flowing into one fingerprint, beside what a signature over a cart alone covers), and "change one thing": the viewer's own browser recomputes the fingerprint and checks the real signature with the approver's public key, and an edited copy fails; real records only (the builder, 14:31; built by the TALK thread) | open |
| K6 | on `/seal/`, "Try to get a cart without her": real attempts against the real routes (no signature; a signature from a key that was never enrolled; an earlier signed request replayed; a change to a limit from the laptop), each showing the server's real refusal, each recorded as a refused attempt; nothing staged (the builder, 14:58: showcase the security and usefulness of the approver) | open |

## GRAPH (the memory as a knowledge graph, on Cognee)
| id | item | status |
|---|---|---|
| H1 | the run's knowledge as a graph built from real records only: people, the home's facts, the order's items and limits, products, stores, strikes, purchases, and who owns each | open |
| H2 | Cognee holds it: a dataset per owner with its permissions; a write to the issuer's dataset by the shopper's side is refused and shown | open |
| H4 | `/graph/` leads with the run as a workflow graph: each step a node with its tool and its real count, products shown by name moving along it and leaving at the rule they fail; the knowledge graph of one decision below it | open |
| H3 | `GET /api/graph?line_id=` (nodes and edges for one item, with which backend answered) and `/graph/` drawing it quietly | open |
| H5 | `/graph/` opens on the run explored as a graph that grows: the order, the searches, every product found as a node, each rule sweeping the products that fail it aside with the reason, web review searches attaching ratings to those that pass, the ranking by the chosen ordering, the signature as the last gate before a cart; Play and step; every node clickable to its text and source; real records only (the builder, 14:31) | open |
| H6 | the exploration also shows what the agent already knew and whom it asked: recalled memories as nodes with owner and age (measurement, earlier strike, earlier purchase, what a store said), the patient's facts from the order as sealed nodes that explain a limit and never travel, and the conversation with the store's agent with the guard's removed parts on the edge; `memory_rows` no longer 0 in `/api/graph` (the builder, 14:38) | open |
| H7 | the surgery as an event the agent already holds, at the root of the graph: `sheets/sheet4_context.json` (invented messages; each fact an exact quote with offsets; `feeds` pointers into the sheet, `equals` checked by code); facts that feed the order light up (discharge date sets the need-by date, 280 lb is why 300 lb, Dana has not seen the house so Elena measures), facts that do not (who drops off, who picks up) stay dim as "held, not used for this order"; each with its sharing class (the builder, 14:45) | open |
| H8 | the limits are prescribed, never derived: in the graph a limit's only source is the order its author wrote and signs; the event context feeds the date, who is at the house and the measurements, and no limit (the builder, 14:58) | open |
| H9 | `/graph/?embed=1&autoplay=1`: canvas only, plays once in about 25 to 30 s, large captions, "Replay of this run's records", posts `signoff:replay-done`; and the six polish points from the integrator's 15:07 screenshots (overlap in the store stage, store answers folded, the event as the root, survivors and gate large, headings, no clock times) | open |

## REVIEWS (what the web says, quoted with its source)
| id | item | status |
|---|---|---|
| R1 | for the products that pass an item's rules: a web search for reviews (Exa), the pages read, and a rating, a review count or one reviewer sentence kept only as an exact quote with its source address; cached; nothing kept that cannot be quoted | open |
| R2 | `GET /api/reviews?line_id=` and an optional `reviews` block per candidate for the screens; reviews never change whether a product passes; "best reviewed among those that pass" offered to the shopper as a choice, not applied silently | open |
| R3 | the step in the run's records (trail feed, outbound ledger: what was sent to the search service, and that no limit, measurement or name was in it) | open |
| R4 | `signoff.reviews.ratings(line_id)` for the engine: `{candidate_id: {rating, out_of, review_count}}` from the cache only, no network; the minimum review count stated | open |

## AIRBYTE / RELAY thread
| id | item | status |
|---|---|---|
| A1 | the sync brings up and tears down its own parts; the tunnel lives only during a run | main |
| A2 | Airbyte follows the active sheet; one run for sheet 2 reported | open |
| A3 | `/relay/` in the product's visual system; screenshots of each state | open |
| A4 | a full Relay pass end to end on a phone, result stored for the signature | open |

## Integrator
| id | item | status |
|---|---|---|
| I1 | main switched to sheet 2 when it holds end to end; sheet 1 intact as the fallback | open |
| I2 | a hand-read sample of `not_stated` and `unclear` on both sheets before any count is said aloud | open |
| I3 | the list of figures behind the final cart for the builder to read himself | open |
| I4 | DEMO.md rewritten from the director's run (surgery lead, class list second); to be checked against the screen at 15:00 | main |
| I5 | SUBMISSION.md and README from what runs (after the sponsor audit) | open |
| I6 | backup clip recorded; three timed rehearsals, one in replay mode with the network off | open |
| I7 | repo public and pushed (needs the builder's yes at 15:45); form submitted by 16:10 | open |
| I8 | a real Senso block shown once (an item that is not on the order) | open |
| I9 | the SingleStore query on screen with a count that matches | open |
| I10 | an Amplitude chart of tool calls by reader arm (needs the builder in the Amplitude console; first confirm events appear there at all) | open |
| I12 | the lead example is sheet 3, the teacher's list (the builder, 13:25); sheet 2 is second and the fallback | ok |
| I13 | main switched to sheet 4 (the lead) when it holds end to end; sheet 3 reachable through the switcher | ok (13:38; sheet 3 through the switcher still to be seen) |
| I14 | the lead example is sheet 4, surgery short; sheet 3 the class list is the 15-second second; the plumber and six-item sheets are not shown (the builder: "your choice", 13:30) | ok |
| I15 | the run of show from the demo director, and the flow designer's spec forwarded to TRAIL and SCREEN | ok |
| I16 | one preference in a real order: sheet 3's notebook ("at least 70 sheets; 100 if they have them") once E31 is on main; decide at 15:20 whether the lead sheet gets one | open |
| I17 | the judge review of 14:43 (`NOTES/REVIEW-judge-1440.md`, 21 items): 1, 2, 5 to 12, 15, 21 to SCREEN; 3, 4, 13, 14 to TRAIL; 16, 17 to GRAPH; 18, 19 to TALK; 20 to SIGN; each checked on main at 15:20; his run of show weighed against the builder's asks when DEMO.md is rewritten | open |
| I18 | three independent reviewers at 15:00 going through everything: the approver path attacked on a copy; every page for design at 1440 x 810 and 150%; the whole story and the day's decisions for coherence and true claims; findings routed and checked (the builder, 14:58) | open |
| I19 | the demo's spine is the approver: the laptop's change refused, the ordering changed by the shopper appearing on the phone before she signs, the signature, carts for exactly the signed picks, one value changed and the check failing; DEMO.md rewritten on that at 15:20 | open |
| I20 | the approver review's six holes (`NOTES/REVIEW-approver-1500.md`): H1, H4, H5 to ENGINE; H2, H3, H6 to SIGN; each with a failing test first; checked on main before the demo | open |
| I11 | every sponsor sentence in DEMO.md, CONTRACT.md's prize table and the submission checked against the 13:25 sponsor audit: no hand-checked sheet, no Gmail connector, no "Amplitude said", no Senso version ids until G15, no Firedrill unless G14, Airbyte is Core with a File source and MySQL staging, not agent connectors | open |

## The builder
| id | item | status |
|---|---|---|
| B1 | Firedrill staff: `native_participant_capacity_exceeded` | open |
| B2 | five minutes each with Senso, Superlinked, SingleStore, Amplitude and Statsig staff: what "best use" means | open |
| B3 | Persona: tell Ellen what we are building with Inquiries and Relay | open |
| B4 | read the figures behind the final cart (I3) | open |
| B5 | revoke the Persona production key; rotate the keys pasted in chat: **after the hackathon ends** (the builder, 13:30) | deferred |
| B6 | look in Amplitude for events from agent `signoff-shopper` and make one chart of tool calls by variant (I10) | open |
