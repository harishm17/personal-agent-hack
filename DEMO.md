# Demo run-of-show

Rewritten 12:05 after two independent reviews. Only what is on main and rehearsed by 14:30 stays in.

## One sentence
Sign-Off is a shopping agent that buys nothing it cannot quote, and nothing at all until the person
responsible signs.

## The story (3 minutes live; the laptop shows the screen, a phone is Dana's)
| Time | On screen | Focal point | Said |
|---|---|---|---|
| 0:00 | The sheet, not signed; the counts | "111 pages read · N never state the deciding figure" (read N from the screen) | "Dad comes home after surgery. His therapist set what the house needs; his daughter shops. Invented family, three real stores. My agent read every page, and threw out every product whose page never states the number that decides." |
| 0:25 | The shower chair: dots flow through the four gates to one pick | the dots falling into "not stated" | "Each dot is a real product page. These never state a width. These are outside her limits. One is left." |
| 0:50 | The pick card: the store's own words, the margin bars | the quoted figure | "The model only reads. Code finds this exact quote in the store's text and does the sums." |
| 1:10 | I drag the capacity limit on the phone | the tick sliding, dots crossing, the pick changing store | "Her limit, from her phone, signed. The pick just moved to another store. No model was asked." |
| 1:35 | On the laptop the shopper asks the agent to change the limit; then the planted page | the refusal; "instruction found, no path to the pick" | "The shopper cannot change it, and neither can a sentence hidden in a store's page." |
| 2:00 | The judge taps Sign on the phone | the seal: signer, hash, what the hash covers, two real cart links | "Only now do carts exist, at the real stores. She signed the limits, the quotes and the picks, not just a total. Nothing is checked out." |
| 2:30 | One sponsor result on screen (the reader gate) and the receipts | "kept" or "switched back", with the numbers | "A small open model on Superlinked reads the same pages; a Statsig gate switches it in, Amplitude records every read, and here is how often the two agree." |
| 2:45 | What is not claimed | | "The figures are what the stores state, not tested facts. The people are invented. No therapist has used it." |
Line to use for the limit drag: the shower chair. Check the exact values on the day: raising the capacity
limit moves the pick from parentgiving.com to carex.com (ENGINE measured 300 to 375 at 11:32).

## Inputs
- Live: cached pool from three real stores, live cart creation on signing, Dana's phone over the tunnel.
- Fallback: `SIGNOFF_MODE=replay` (cached store responses, labelled on screen; checks still live); the
  backup clip on the Mac; Dana's view in a second browser window if the phone cannot reach the app.

## Tools named out loud (only those with a real call in the demo path at 14:30)
| Tool | Its job | Said |
|---|---|---|
| SingleStore | product pool and every decision record; one SQL statement returns the candidates inside the limits | "The audit trail is a table; this query is the third gate" |
| Superlinked SIE | a small open model reads the same pages; agreement with the reference reader is measured | "A small model agrees with the large one on 166 of 169 figures" (read the number from the screen) |
| Statsig + Amplitude | the gate switches the reader; every read and check is a recorded event | "Shipped behind a gate, measured, kept or switched back" |
| Senso | holds the therapist's order with version ids; checks each sentence of the sheet against it before the signature | "Senso checked the sheet against her order before she could sign" |
| Persona | the signer's identity inquiry; its id is in the signature record | "Sandbox, so it always passes; the seal says so" |
| Airbyte | a local sync delivers the stores' records to the database | "Airbyte, running on this laptop, delivered these rows" |
| Firedrill | simulated shoppers attack the limits and the signature; exact checks on state | only if a campaign ran: what it found and what we changed |

## Questions and answers
| Question | Our answer (short, true) |
|---|---|
| What is real and what is invented? | Real: the three stores, product text, prices, the store agents' replies, the carts. Invented and labelled: the father, the home, the daughter, the therapist and her order, and one planted test page. |
| How do you know the model read the figures right? | Every figure must be an exact quote found in the store's text by code, and a second model reading the same pages agrees on 166 of 169. There is no hand-labelled ground truth; I read the figures behind the cart myself. |
| Could an existing personal agent do this with a prompt? | It can shop and compare. Its owner is root, so it cannot hold a limit the owner may not edit or need another person's signature. |
| Isn't this an approval workflow? | The approval is the smallest part. The search, the figures and the cart are bound by another person's limits in code, and the signature covers the evidence, not only the cart. |
| What about prompt injection from a store page? | The reading model has no tools and its output is typed and checked, so store text can change a value but not what the agent does. The planted page shows it. |
| She can just buy it herself. | Yes. Then it is not under the therapist's signature, and the sheet says so. |
| Is the stated capacity true? | It is the maker's claim. The sheet says "states". |
| Why are no vivehealth products picked? | Its agent states no delivery time, and the shopper's rule needs one. |
| What was built today? | All project code, from 11:00. Research, the spec and the starter kit were preparation. |

## Keys and setup before going on stage
- [ ] 16:50: `sh scripts/run_main.sh`, open http://localhost:8800, tunnel up, phone on the tunnel address
- [ ] `POST /api/admin/reset`; browser zoom set for the projector; the Statsig console open in a tab
- [ ] Replay mode rehearsed once with the network off; hotspot ready
- [ ] Backup clip on disk; video link opens while logged out

## Rehearsal log
| Time | Duration | What broke | Fixed |
|---|---|---|---|
| 11:46 | n/a | First real phone run by the builder over the tunnel: 71 signed requests, signed, two real carts. Nothing broke. | |
