# Demo run-of-show

## One sentence
A shopping agent that buys under someone else's limits and signature: the person who knows sets limits the
shopper cannot edit, the store's own words decide each line, and the cart exists only when that person signs.

## The story (3 minutes live; the big screen is the one screen, a judge holds Dana's phone)
| Time | On screen | Focal point | Said |
|---|---|---|---|
| 0:00 | The sheet: six empty tiles, the seal | "No cart exists at any store" | "Every personal agent has one boss: its owner. This one shops under limits its owner cannot edit. Invented family, real stores. Dad comes home after surgery." Hand a judge the phone: "You are his therapist." |
| 0:20 | Tiles fill from three real stores; one stays dashed | The counter | "Real products from three stores. The ones that never state a capacity are out, and it says so." |
| 0:40 | The toilet seat opens; the sums appear | The sum | "Blue, Elena measured. Amber, the store's sentence. Violet, your limit." |
| 1:05 | The store's sentence | the stated range | "The store states a range. Code takes the end that could fail." |
| 1:20 | The judge drags capacity up on the phone | The blue ring jumping between dots | "Dots go grey and the pick moves to another store. The model was not asked." |
| 1:50 | The judge strikes a line; on the laptop: "put it back" | The refusal | "It cannot. Only you can." |
| 2:10 | The judge signs | The seal, then the store's own cart page | "Only now does a cart exist. This store will not take a bath seat back, which is why she signs first. No checkout." |
| 2:35 | Sheet 2, a labelled replay | The same box with kitchen limits | "Same engine, two flatmates and a kitchen." |
| 2:45 | The counts strip | The measured counts | The counts, then what is not claimed. |
If sheet 2 is not recorded by 15:30, drop the switch and keep the sentence.

## Inputs
- Live: three real stores (cached pool, live cart creation), Dana's phone over the tunnel, Elena's laptop.
- Fallback: `SIGNOFF_MODE=replay` (cached store responses, labelled, checks still live); the backup clip on
  the Mac's disk; the therapist's view in a second browser window if the phone cannot reach the app.

## Tools named out loud
| Tool | Moment | Said |
|---|---|---|
| Superlinked SIE | the store's sentence | "Every amber number on screen is a span in the store's own text" |
| SingleStore | the candidate plot | "The audit trail is one table; this query is the passing box" |
| Senso | before the signature | "Senso checked each sentence of this sheet against the order and the store's policy before she could sign" |
| Persona | the seal | "The key belongs to a checked person, not to my agent" (sandbox, labelled) |
| Amplitude + Statsig + Arcee | counts strip | "We shipped a cheaper reader behind a gate, measured it against the hand-checked sheet, and kept it or switched back on the numbers" |
| Airbyte | opening | "Her order arrived as an email; the limits were proposed from it and she confirmed them" |
| Firedrill | counts strip | "The attacks were not written by me" |

## Questions and answers
| Question | Our answer (short, true) |
|---|---|
| What is real and what is invented? | Real: the three stores, product text, prices, the store agents' replies, the carts and their links. Invented and labelled: the father, the home, the daughter, the therapist and her order. A Persona sandbox check always passes. |
| Could Muse do this with a good prompt? | It can shop and compare. It cannot hold a limit its owner may not edit or need a second person's signature, because its owner is root. |
| Isn't this an approval workflow? | The approval is the smallest part. The agent's search, its figures and its cart are bound by another person's limits in code, and the proof for each line is the store's own sentence. |
| She can just buy it herself. | Yes. Then it is not under the therapist's signature, and the sheet says so. |
| What happens when the model is wrong? | A figure counts only if its quote is found in the store's text at the stated place. Code does every comparison. A missing figure rejects the product. |
| Is the stated capacity true? | It is the maker's claim. The sheet says "states". |
| How was the number measured? | Against a 30-product sheet filled in by hand today; the count is from code. |
| Has a therapist used it? | No. |
| What was built today? | All project code, from 11:00. Research, the spec and the starter kit were preparation. |

## Keys and setup before going on stage
- [ ] 16:50: warm SIE, open the app at `http://localhost:8000`, tunnel up, phone on the tunnel address
- [ ] `POST /api/admin/reset`, browser zoom checked on the projector
- [ ] Replay mode rehearsed once with the network off; hotspot ready
- [ ] Backup clip on disk; video link opens while logged out

## Rehearsal log
| Time | Duration | What broke | Fixed |
|---|---|---|---|
