# Approver review, 15:00

Independent security review of the approver path. Code at `818ba31` (the reviewed files are unchanged at `dc5293d`).
Every attack ran against my own copy: a temporary worktree, port 8033, `SIGNOFF_MODE=replay SIGNOFF_SHEET=sheet4`,
started with an empty home folder so no key file was read (no Persona, no Senso, no database, no store). The live
instance got two GETs (`/api/issuer/status`, `/api/issuer/enroll-code` with a tunnel header: 403). The worktree is removed.
"Outside" means the request carried `cf-connecting-ip: 203.0.113.9` or `x-forwarded-for: 203.0.113.9`.

Verdict in one line: **nobody without her key got a cart, a signed state or a changed limit, by any route I tried
(42 requests).** The holes are at the edges: what her screen shows that the hash does not cover, two ways an outsider
can stop her (not replace her), and a signed request that stays usable after a refusal.

## Holes (fix these first)

| # | Hole | Evidence | Fix | Seen in a 3-minute demo? |
|---|---|---|---|---|
| H1 | **The product name she reads is not under the hash.** The canonical pick has store, product id, variant id, product key, variant title, price, quantity, currency, but no `title`. The phone takes the title from `/api/state` (`web/phone/index.html:299`: `p.title \|\| cand.product.title`). A wrong or altered title with the same ids signs to the same fingerprint. | `GET /api/sheet/canonical` pick keys: `checks, currency, delivery, id, price_cents, product_id, product_key, quantity, quotes, store, variant_id, variant_title`. | **S**: add `"title": p["title"]` to the pick in `_canonical_obj` (`signoff/engine/state.py:584`) and "product name" to `COVERS`; the phone already prefers `p.title`. Every hash changes, so re-run the tests that pin one. | Only if a judge asks "is the name signed?" Today the honest answer is "the product and variant ids are, the name is not". |
| H2 | **Five wrong codes from anywhere lock enrolment for everyone, including the right code.** An outsider with the tunnel address can keep her from ever enrolling. | After a reset, 5 × `POST /api/issuer/enroll {code: wrong}` from outside → 403 `bad_code`; then the **right** code from the laptop → `429 code_locked`. | **S**: make the code long (`secrets.token_hex(8)`, it travels in the link anyway) and drop the global lock; or count wrong codes per `cf-connecting-ip`. | Yes if someone does it while the phone is being enrolled live. Enrol before the talk. |
| H3 | **`POST /api/issuer/persona/start` is open from outside** (not on the guard list, no signature). With Persona configured, each call makes a new inquiry and replaces the current record, so an outsider can turn a passed identity check back into "not finished" just before she signs, and gets the link to complete the new inquiry as anyone. | From outside: `POST /api/issuer/persona/start` → `200` (my copy has no Persona key, so it answered `configured: false`; the replacement is read from `persona.py:69-87`, **not run**). | **S**: refuse a new inquiry while the current one is verified, and when no key is enrolled. **M**: make it a signed request from her key. | Yes if attacked: her sign tap answers `identity_not_verified`. |
| H4 | **A sign request that was refused is not burned.** `stale_hash` is raised before the sequence number is recorded, and `identity_not_verified` rolls it back. Whoever holds the request (the laptop does) can send it later, if the sheet is back at that hash, and the sheet is signed with nobody tapping. The content is what she signed; the moment is not hers. | Signed over `3c79cb17…`; shopper's choice changed → `409 stale_hash`; choice reverted; **the same request** → `200 applied: sign_sheet`, 3 carts. Also: the same identity-refused request sent twice → `403 identity_not_verified` both times, never `replayed_seq`. | **S**: in `verify.py` record `last_seq` before the stale check (lines 203-205), and do not roll back on `identity_not_verified`; the phone always sends a higher number. Optional: refuse an `at` older than two minutes. | No. |
| H5 | **The same limit value can have two fingerprints.** The canonical text keeps the number as typed: `16.0` from the sheet file, `16` after a signed change back to 16. | `L5.length` 16.0 → 20 → 16: hash `3ac94ba1…` before, `3c79cb17…` after, same sheet. | **S**: `float(value)` in `_number` (or format the bound with `%g` in `with_bound`). | **Yes**, if anyone says "put it back and the fingerprint comes back". True for the 300 lb limits, false for the 16 in one. |
| H6 | **The armed Sign button survives a change.** First tap arms for 4 s; if the sheet changes in that window the page re-renders with the new sheet and the second tap signs the new hash (`armedUntil` is only cleared on a tap). She signs what is on screen, but has not read it. | Code read (`web/phone/index.html:399-405`), **not run** (needs a browser). | **S**: set `armedUntil = 0` and show "The sheet changed" whenever `canon.hash` changes. | No. |

## 1. A cart or a signed state without her: HOLDS

| Attempt | Request | Response | Verdict |
|---|---|---|---|
| Empty body | `POST /api/issuer/request {}` | `401 unsigned` | HOLDS |
| Payload, no signature | `{payload: sign_sheet…}` | `401 unsigned` | HOLDS |
| My own key, nothing enrolled | signed `sign_sheet` | `401 no_key` | HOLDS |
| My own key, her enrolled, my key id | signed `sign_sheet` | `401 unsigned` | HOLDS |
| My own key, her key id | signed `sign_sheet`, `key_id` hers | `401 unsigned` | HOLDS |
| Her signature, payload altered (350 → 600) | `set_limit` | `401 unsigned` | HOLDS |
| 64 zero bytes as signature; empty signature | `sign_sheet` | `401 unsigned` | HOLDS |
| Her signature, another sheet id | `sheet_id: sheet2` | `409 wrong_sheet` | HOLDS |
| Her signature over a different hash; over no hash | `sheet_hash: 000…`; none | `409 stale_hash` | HOLDS |
| Unknown action | `type: mark_signed` | `400 bad_payload` | HOLDS |
| Replay of an applied request | same `set_limit` body again | `409 replayed_seq` | HOLDS |
| Lower sequence number; a string | `seq: 5`; `seq: "999…"` | `409 replayed_seq`; `400 bad_payload` | HOLDS |
| An earlier sign request after later requests | captured body, seq below the last | `409 replayed_seq` | HOLDS |
| Signed, then a limit changed, then sent | `sign_sheet` over the old hash | `409 replayed_seq` (the limit change used a later number) | HOLDS |
| Signed, then a measurement changed | `POST /api/shopper/fact` between | `409 stale_hash` | HOLDS |
| Signed, then the ordering changed | `POST /api/shopper/pick_rule {best_reviewed}` between | `409 stale_hash` | HOLDS |
| Signed, then the shopper's choice changed | `POST /api/shopper/choose` between | `409 stale_hash` | HOLDS |
| The same request after the change is undone | as above | `200`, signed | **HOLE H4** |
| Shopper chooses past a limit | `choose` a product marked outside | `409 that product cannot be chosen: it is outside (31 <= 21.5 is false)` | HOLDS |
| Out-of-range and not-hers limits, signed by her | `value: 5000`; `L1.tub` | `400 out_of_range`; `400 not_an_issuer_limit` | HOLDS |
| A change racing the store calls | hold in `signed_picks`, re-check in `mark_signed` | unit tests pass (`test_a_sheet_that_moves_while_signing_is_not_signed`) | NOT TESTED by request (timing); code and tests read |

## 2. Taking over the approver

| Attempt | Request | Response | Verdict |
|---|---|---|---|
| Read the code from outside | `GET /api/issuer/enroll-code` with `cf-connecting-ip`, `x-forwarded-for`, `cf-ray`, empty or guessed `x-admin-token` | `403 local_only` (all five; also on the live instance) | HOLDS |
| Enrol without a code; wrong code | `POST /api/issuer/enroll` | `403 bad_code` | HOLDS |
| Second key with the right code | same code, new key | `409 already_enrolled` | HOLDS |
| Reuse the code after a reset | previous run's code | `403 bad_code` | HOLDS |
| Her old key after a reset | signed `sign_sheet` | `401 no_key` | HOLDS |
| Reset from outside | `POST /api/admin/reset` with either header | `403 local_only` | HOLDS |
| Path tricks from outside | `//api/admin/reset`, `/API/…`, `/api/%61dmin/reset`, `/api/admin/../admin/reset`, trailing slash | `404`, `404`, `403`, `403`, `403` | HOLDS |
| Shopper and admin routes from outside | `shopper/pick_rule`, `shopper/fact`, `admin/use-sheet` | `403 local_only` | HOLDS |
| Admin simulate from outside | `POST /api/admin/persona/simulate {approve}` | `403 local_only` | HOLDS |
| Sign with identity not passed | her valid `sign_sheet`, gate on | `403 identity_not_verified` | HOLDS |
| Lock her out | 5 wrong codes | right code → `429` | **HOLE H2** |
| Start an inquiry from outside | `POST /api/issuer/persona/start` | `200` | **HOLE H3** |
| Bypass the gate with a real approved inquiry | needs a Persona key | | NOT TESTED (no key on my copy by design) |

Read, not a hole but say it if asked: the guard trusts the proxy headers, so it holds for a tunnel that adds them
(cloudflared, ngrok) and would not for a plain port forward. From the laptop itself, reset, the code and "simulate
approve" are all open: **the laptop can replace her** (reset → enrol a new key → simulate → sign). What shows it: her
phone says "A new run started", and the seal carries a different key id. Limit changes and strikes need her key but
not the identity check; only the signature does. Her name is typed at enrolment and the seal says "(self-declared)".

## 3. What is and is not under the hash

Covered (changing any changed the hash on my copy, or is in the canonical text): sheet id; ordering id, label and
`within`; per line: need, status, fulfilment, each limit's id, operator, unit, value and who set it, struck product
keys, `picked_by`; per pick: store, product id, variant id, product key, variant title, price, quantity, currency,
each check as an expression, the store quotes, the delivery quote with its day range and need-by date; the total.
`preferences` join when the sheet has them (sheet4 has none: NOT TESTED by request; unit test present). The rating
joins only under a review ordering: the key is present for `best_reviewed`, `best_value`, `most_popular` (plus
`review_count` for `most_popular`) and absent for `cheapest`, where it plays no part. HOLDS.

**Shown at signing, not covered:**
- the product name (H1), on the phone and the laptop;
- the wording of each limit and the order's sentence (from the sheet file; only id, operator, unit and value are hashed);
- the identity label and the Senso verdicts (in the signature record, not in the hash);
- the reason for a strike (only the product key is hashed).

**On the laptop screen, not covered:** the product picture and page link, the return policy quote (`undo`), the
"picked because" sentence, the products that were not picked, when the page was fetched, shipping and tax (the total
is the sum of unit prices; the store's own total is compared afterwards).

## 4. What she sees against what she signs

HOLDS, with H1 and H6 as the gaps. The phone fetches the canonical text, hashes it itself, refuses to sign when its
hash differs from the server's, draws the review from that same text, and signs a message naming its own hash
(`hashNow`, line 150). On my copy `sha256(canonical) == sheet_hash` and the signed message names that hash. The
fingerprint on the seal is the first 12 hex characters of the same hash. The limit is that the page itself comes from
the same server: a server that serves a different page can show anything. NOT TESTED in a browser.

## 5. After signing

| Attempt | Response | Verdict |
|---|---|---|
| The same sign request again; a fresh one | `409 replayed_seq`; `409 already_signed` | HOLDS |
| Signed limit change; signed strike | `409 already_signed` | HOLDS |
| Measurement, ordering, choice from the laptop | `409 this sheet is signed and its carts exist; reset to start again` | HOLDS |
| Hash and carts after all of the above | unchanged, `seal.current: true` | HOLDS |
| Carts for exactly the signed picks | 3 signed picks at 3 stores → 3 carts, each store's signed total equal to the cart total, `lines_checked: true` | HOLDS (replay) |
| The store's cart differs | unit tests pass (47 in `tests/sign`: price, quantity, added and dropped lines, totals shown with both numbers) | NOT TESTED by request (replay never differs) |

Know this before a judge asks: a differing store cart is **shown, not blocked**. The seal stays signed and the cart
link stays, with "store total differs: signed $x, store $y".

## Second half: the three best live demonstrations

1. **"Sign, then the family changes its mind."** (about 25 s) On the laptop, change the ordering to "best reviewed"
   right after she taps Sign on the old sheet, or simply show the phone after the change. Screen: her tap answers
   "The sheet changed after you looked. Check it and sign again"; no cart exists. Say: "Her signature is for one
   exact sheet; change anything about what is bought and it is worth nothing." This is the strongest one because it
   is the real risk (the agent or the family moves the order after approval) and it needs no explanation of keys.
2. **"Try to get a cart without her."** (about 20 s) On `/seal/`, press the buttons: no signature, a stranger's key,
   her earlier request again. Screen: three refusals with their codes (`unsigned`, `unsigned`, `replayed_seq`) and
   the line "No cart exists at any store". Say: "The agent can shop all day; it has no way to buy."
3. **"Change one thing."** (about 20 s) On `/seal/`, tap the 300 lb limit, type 250. Screen: the fingerprint
   changes and her signature turns from "verifies" to "does not cover this". Say: "Your browser just checked her
   signature itself; you do not have to trust our server." Third because it proves integrity after the fact, which
   judges believe more easily than they believe a refusal.

Yes, those two `/seal/` pieces are the right two. For them to be honest:
- "Change one thing" must run the check in the browser over the canonical text as served (it does: `verify.js`
  splices the text, so bytes are kept), and must only offer values that are in the canonical text. **Do not show the
  product name as editable or as covered until H1 is fixed**; today the page lists the product key, which is right.
  Do not say "change it back and it matches" about a number written `16.0` (H5); the page's splice keeps the bytes,
  the phone's slider does not.
- The public key comes from the same server as the proof. Say "her key was enrolled at the start with a code shown
  only on this laptop" and show that the key id on the seal equals the one on her phone.
- "Try to get a cart" must fire real POSTs at `/api/issuer/request` and show the server's real answer, never a
  canned one. Use a key generated in the page for the stranger. Send `sign_sheet` attempts only **before** she has
  signed (after, every answer is `already_signed`, which proves less) and never a valid request of hers. A replayed
  request can be shown from the receipt log. The attempts are logged as refused receipts; say so, it is a feature.
- Use a sequence number in the replay button that is really an old one of hers; a made-up body only shows `unsigned`.

## What this does not protect against (three lines for a judge)

- **Her phone or the laptop.** Whoever holds her unlocked phone signs as her (the key cannot be copied out, but it
  can be used); whoever sits at the laptop can reset and enrol a new approver, and the identity check is a sandbox.
- **A therapist who does not read.** The signature proves which sheet she approved, not that she understood it.
- **A store whose page is wrong.** The quotes are the store's own words, checked for being there, not for being
  true; and the product name is not yet under the hash (H1). A cart that differs from the signed picks is shown, not stopped.
