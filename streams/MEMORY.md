# Stream MEMORY

You are the MEMORY stream at a timed hackathon (deadline 16:30 today; feature freeze 15:00). Use the
hackathon-stream skill. First run `./hk own MEMORY`. Then read CONTRACT.md (skim the body; read the
amendments from 13:10 on carefully), OPEN.md (your items are M1 to M4) and the AGENTS.md quirks log.
**Time box: M1 and M2 on your branch by 14:20, M4 seen working by 14:35. Anything later is cut.** Say in
NOTES/INTEGRATOR.md by 14:10 if that will not hold, and what the smallest honest version is.

## Why this stream exists
The builder, at 13:55: "I definitely want some context engineering and memory here. It is the biggest point
in building agents and AI, no?" He is right that the build has none: every run starts from nothing. The
product ("Sign-Off") shops real stores to another person's written order and buys only on that person's
signature; the lead example is a therapist's equipment order (sheet 4: shower chair, walker, grab bar) that
a patient's daughter shops. The honest gap: the home was measured this morning, the therapist struck a
product and said why, three stores told us their delivery and return terms, and a reset forgets all of it.

## What to build: owned, sourced memory
The idea in one line: **the agent remembers only what a real record proves, and every memory has an owner.**
Research the project read today found that agent memory is easy to poison ("all memory systems are
susceptible", MemoryDojo) because anything the model reads can become a memory. Here nothing a model reads
or writes becomes a memory: a memory is created only from a record in the receipt chain or the saved store
replies, and it keeps who owns it.
1. **The store (M1).** `signoff/memory/`: one row per memory: `{id, owner (issuer, shopper or a store's
   domain), kind (home_measurement, strike, store_answer, purchase), key, value, text (one plain sentence),
   source: {receipt hash or file and time}, created_at, sheet_id}`. Written by reading what already exists:
   the receipt chain (`signoff/engine/receipts.py`, `GET /api/receipts`: shopper facts set, strikes accepted
   with their reasons, sheets signed), and the saved store answers (`data/**/store_answers/`, with the time
   asked). Persist in SingleStore (database `signoff`, your own table `memory`; connection as in
   `signoff/db/`) with a local JSON-lines mirror under `data/memory/` so the app works with the database
   down. A write is refused unless it names a real source record; a strike or anything owned by the issuer
   needs a receipt of a verified signed request. Tests prove a made-up memory and an issuer memory without
   a signed receipt are refused.
2. **Recall on a new run (M2).** `signoff.memory.recall(sheet: dict) -> dict` (never raises): the home's
   measurements for the facts this sheet uses (value, who measured, when), the issuer's earlier strikes by
   `product_key` with their reasons and dates, and each of the sheet's stores' answers with their age.
   `signoff/memory/api.py` exporting `router` (optional in the app, already listed): `GET /api/memory`
   (everything, grouped by owner, with sources) and `GET /api/memory/recall?line_id=` (what was recalled for
   one item and why). ENGINE is adding two hooks (E28) so a reset or a switch of sheet applies what
   `recall` returns; agree the exact shape with ENGINE in NOTES/ENGINE.md first, in one short note.
3. **Recall by meaning, and what each model call was given (M3).** For an item, find the memories relevant
   to it: embed each memory's sentence and the item's need with Superlinked SIE (`sie-sdk`, `SIE_API_KEY`,
   `client.encode("Qwen/Qwen3-Embedding-4B", [{"text": ...}])`, see AGENTS.md and
   `/Users/harishm/research/2026-11-20-tokensand-personal-agents-hackathon/research/sponsors-data.md`
   section 2) and rank with SingleStore vector search (`VECTOR(n)`, `<*>`), filtered in the same SQL
   statement by owner and kind. Return "N recalled of M" with scores. Add what context each model call was
   given and not given, from the outbound ledger (`GET /api/egress`): the reading model is given one page
   and the figure meanings and no memory at all; say so with the real counts.
4. **A second run, shown (M4).** In replay mode on your own port: run sheet 4, change a home measurement,
   strike a product as the issuer with a reason, sign; then reset. The new run must show the measurement
   remembered (with who and when), the struck product out without anyone striking it again and marked
   "struck before" with the reason, and the stores' answers reused with their age. Save the two states and
   write `DONE M4: <proof>`.

## You own
`signoff/memory/**`, `tests/memory/**`, `data/memory/**`. Everything else: `NOTES/<OWNER>.md`. Develop on
port 8007; main is 8800 (GET only there). The SCREEN and TRAIL streams draw; give them the shape of
`GET /api/memory` and `/api/memory/recall` in NOTES/SCREEN.md and NOTES/TRAIL.md as soon as it is stable.

## Rules
The working path is not changed: you read records and you offer `recall`; you never write engine state.
No special cases, no lists of products or stores, no silent fallbacks (if the database is down the reply
says the mirror was used). Tests that call SingleStore or SIE get `@pytest.mark.live`. No AI or tool
authorship lines in commits, docs or code. Close each item with `DONE M<n>: <proof>` in
NOTES/INTEGRATOR.md. Commit small and often to `stream/MEMORY`. Do the work yourself; start no new threads.
