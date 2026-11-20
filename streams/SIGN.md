# Stream SIGN (sign and eval)

You are the SIGN stream at a timed hackathon (deadline 16:30 today). Use the hackathon-stream skill.
First run `./hk own SIGN`. Then read CONTRACT.md ("Signed request" first) and the AGENTS.md quirks log.
Sponsor notes: `/Users/harishm/research/2026-11-20-tokensand-personal-agents-hackathon/research/sponsors-infra.md`
(section 4, Persona) and `.../research/sponsors-context.md` (section 1, Senso).

## You own
`signoff/sign/**`, `web/phone/**`, `evals/**`, `tests/sign/**`. Everything else: request changes in
`NOTES/<OWNER>.md`. Develop on port 8004.

## Build, in this order
1. **Keys, signatures and the phone (by 12:00; "a second phone signs" is a first-hour test).**
   `web/phone/index.html`, plain HTML and JS, for a phone held by a judge: on first open it makes an ECDSA
   P-256 key pair with WebCrypto (private key not extractable, in IndexedDB) and enrols it. Three views:
   limits (one slider per issuer-set limit, sending a signed `set_limit` as it moves, at most ten a
   second), lines (accept, or strike the picked product with a reason), sign (the sheet in words, its
   hash, one button; the total is computed, never typed). `signoff/sign/api.py` exporting `router`:
   `POST /api/issuer/enroll`, `POST /api/issuer/request`, `POST /api/admin/reset`; `signoff/sign/verify.py`
   checks the signature, `seq` and, for `sign_sheet`, the hash, then calls `signoff.engine.state` or
   `signoff.store.cart.create_carts`. Until the ENGINE stream is merged, code against the function
   signatures in CONTRACT.md with a small stand-in of your own under `tests/sign/`. Unit tests: a forged
   signature, a replayed `seq`, a stale hash and an unsigned request are all refused.
2. **The hand-check sheet (by 11:50; the builder fills it in and it grades the reader).**
   `python -m signoff.sign.handcheck` (or a page at `/handcheck/`) picks 30 products across the three
   stores from `data/pool/*.json` (the STORE stream writes it by about 11:45) and shows each product's
   store text with three inputs: weight capacity, seat or added height, overall width, each a number or
   "not stated". It saves `evals/handcheck.jsonl`. Make it fast to fill in on a laptop. Tell the
   integrator in `NOTES/INTEGRATOR.md` the moment it is ready.
3. **Persona (12:20).** `POST /api/issuer/persona/start` creates an Inquiry and returns the hosted link;
   `GET /api/issuer/persona/status` reads the status from Persona. The signature record carries the
   inquiry id and status; the screen labels it "sandbox". Keys: `PERSONA_API_KEY`, `PERSONA_TEMPLATE_ID`
   (may arrive late; the flow must work without them and say "identity not checked").
4. **Senso (first call as soon as `SENSO_API_KEY` is in the keys file).** One `POST /org/evals/text` on a
   sentence about a store's return policy, to learn whether claims about other brands get a verdict;
   write the answer in the AGENTS.md quirks log through `NOTES/INTEGRATOR.md`. Then load the therapist's
   order, a handout and each store's policy text (raw text, asynchronous), check every sentence of the
   sheet, and block `sign_sheet` on "conflict" or "unsupported". `GET /api/senso/checks`.
5. After 13:10: the 40 pressure attempts (written by a different agent than the one that wrote the
   engine's chat) with `./hk eval`, and `evals/report.md`.

## Interfaces you provide / consume
- Provide: the SIGN routes, `/phone/`, `evals/handcheck.jsonl`.
- Consume: `signoff.engine.state.apply_issuer`, `sheet_hash`, `canonical_sheet`, `mark_signed`, `reset`,
  `set_senso`; `signoff.store.cart.create_carts`.

## Done when
`uv run -q pytest -q -x` is green; from a phone on the tunnel address: enrol, move a limit (the pick on
the big screen changes), strike, sign; the seal shows signer, time, hash and a real cart link.

## Sync points
11:50 hand-check sheet ready · 12:00 a second phone signs · 12:20 first sync · 13:10 end-to-end run ·
15:00 feature freeze · 15:30 code freeze.
No AI or tool authorship lines in commits, docs or code. Commit small and often to `stream/SIGN`.
