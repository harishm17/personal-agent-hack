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
| E1 | `==` as a real comparison; an unknown op or pick rule is an error | main |
| E2 | units gpf and gpm | open |
| E3 | order document and derived limits per sheet (`order_doc`) | open |
| E4 | store replies and the instruction scan per sheet; one path rule, no hard-coded `sheet1` | open |
| E5 | pick rule by id (`cheapest` for sheet 2; sheet 1 unchanged) | open |
| E6 | names, not pronouns, in the chat | open |
| E7 | rule 1: every stated value is tested; new status `unclear`; a number with no unit is `unclear` | open |
| E8 | rule 2: every option on sale is its own candidate (needs S1) | open |
| E9 | rule 3: a limit is compared as the order's sentence is written (at least, at most, equals, fits) | open |
| E10 | figure meanings live in the sheet; no built-in glossary; the prompt asks what the page states, not an "exact measure" | open |
| E11 | planted page out of the live state by default; its wording out of the scan prompt and pattern; `instruction_scan` key | open |
| E12 | readers: `disagreements`, `extra`, `picks_changed`; agreement reported after the rules, unclear ones counted | open |
| E13 | sheet 2 read end to end; report per item (candidates, inside, outside, unclear, not stated, pick) | open |
| E14 | sheet 1 re-read under the three rules; before and after per item | open |
| E15 | `image_url` passed through on `product` (needs S4) | open |
| E16 | `obs.egress` called for every model call (reader, SIE, chat) | open |
| E17 | fixture fallback in `extract/run.py` removed or shown in `degraded` | open |
| E18 | sheet 1's figure meanings, in the order's words, sent to the integrator for `sheets/sheet1.json` | open |
| E19 | receipts for every state change; `GET /api/receipts/verify` | main |
| E20 | seal race, hash covers pick rule, delivery quotes, quantity, currency, variant; scope; `degraded` | main |

## STORE
| id | item | status |
|---|---|---|
| S1 | both pools carry every in-stock option (`options`) | open |
| S2 | brand list and per-type word lists removed; products kept by the store's own category; questions built from the sheet line | open |
| S3 | store agents asked about delivery and returns only | open |
| S4 | `image_url` on every product | open |
| S5 | outbound ledger counts from the saved log, for the active sheet | open |
| S6 | `parse_reply`: a reply that says the store does not say is "unclear" | open |
| S7 | `create_carts` with `timeout_s` and `tries`; one real cart test at each sheet 2 store that has a pick | open |
| S8 | SQL for the active sheet agrees with the engine (==, units, unclear) | main |
| S9 | `/api/gate/status`: decision "switched back" with the evidence fields | open |
| S10 | a local log of tool-call events with timings for the trail (`signoff.obs.recent()`) | open |
| S11 | Amplitude: do home measurements, limits or the order's text ride along in events? Answer and set the content mode | open |
| S12 | replay mode for sheet 2 | open |
| S13 | Amplitude: the gate's variant attached to the session from its start (`experiments` is null now); both arms run once; delivered counts checked (only 2 events were delivered in the 13:25 run) | open |
| S14 | the gate's verdict re-run after the three reading rules; it says "kept" or "switched back" from the numbers, with the evidence; no line claims Amplitude decided it | open |
| S15 | `/api/sql/passing-box?source=airbyte` runs the same statement on the rows Airbyte delivered (`airbyte_pool`), only if under 20 minutes; otherwise WONTDO and the claim is "delivered beforehand" | open |

## SIGN
| id | item | status |
|---|---|---|
| G1 | the sign tap answers within about 8 s; Senso runs in the background, never inside the tap | open |
| G2 | enrolment needs the laptop's one-time code | ok |
| G3 | one answer for an unsigned request | main |
| G4 | display binding: the phone hashes `/api/sheet/canonical` itself and renders the review from it | open |
| G5 | carts created for exactly the engine's signed picks | open |
| G6 | cart lines compared with the signed picks; "store total differs" shown with both values | open |
| G7 | Persona as a gate: signature refused until the inquiry is approved; decline and approve shown | open |
| G8 | review-and-sign phone: no sheet 1 assumptions, the decision screen's tokens, sentence case | open |
| G9 | Senso documents and sentences for sheet 2 | open |
| G10 | receipts for every signed request, enrolment, Persona and Senso result | open |
| G11 | `obs.egress` for every Senso, Persona and Firedrill request | open |
| G12 | the Relay result on the signature record (`relay`) | open |
| G13 | screenshots of every phone state at 390 x 844, looked at | open |
| G14 | Firedrill: retry until 14:00; if it runs, a campaign and what it found; if not, Firedrill is not claimed | open |
| G15 | Senso: resolve and show the `version_id` of the order document beside each verdict (rows carry `content_id` only) | open |
| G16 | `PERSONA_REQUIRED` on by default for the demo sheet once G7 works; Relay's sandbox passes with nobody present: say "sandbox" beside it | open |

## SCREEN
| id | item | status |
|---|---|---|
| C1 | the product-list screen, static pass (order document, cheapest-first rows, why-this-one, signature) | open |
| C2 | the stepper of the run and a drawer per step (from `/api/trail`) | open |
| C3 | motion: rows checked top to bottom; a limit change re-checks cells and moves the highlight; signing | open |
| C4 | statuses outside, unclear, not stated visibly different; option rows; images | open |
| C5 | scale and zoom: 150% and 1920 x 1080 | open |
| C6 | signature block: QR and one line; receipts as ticks with a count; signed state with "self-declared" or "identity checked (sandbox)" | open |
| C7 | the unsigned-change control answering in a toast; tabs Decision and Trail; reader chip "switched back" | open |
| C8 | Detail view, dots, rulers, trays and tiles removed | open |

## TRAIL
| id | item | status |
|---|---|---|
| T1 | `GET /api/trail`: real records only, each with `step` and `kind` (evidence, reading, check, approval, action) | open |
| T2 | `/trail/`: the seven steps as a timeline, events one line each, side sheet with quote and hash | open |
| T3 | the decision screen's visual system; no dots, no arrows | open |

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
| I4 | DEMO.md rewritten for the plumber story and the new screen | open |
| I5 | SUBMISSION.md and README from what runs (after the sponsor audit) | open |
| I6 | backup clip recorded; three timed rehearsals, one in replay mode with the network off | open |
| I7 | repo public and pushed (needs the builder's yes at 15:45); form submitted by 16:10 | open |
| I8 | a real Senso block shown once (an item that is not on the order) | open |
| I9 | the SingleStore query on screen with a count that matches | open |
| I10 | an Amplitude chart of tool calls by reader arm (needs the builder in the Amplitude console; first confirm events appear there at all) | open |
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
