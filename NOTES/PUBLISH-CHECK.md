# Publish check

**Verdict: NOT SAFE as it stands, for one reason that takes a minute to clear; SAFE on keys.** No key value from either env file is in any tracked file, any commit on any ref, or any untracked file. But the live tunnel address and the current enrolment code can be read from the QR code in 10 tracked screenshots (9 already on the remote `main`), and the approver's phone is not enrolled right now: once the repository is public, anyone can scan one and enrol as Dana on the live app. Clear it (below, "The one blocker") and it is safe.

Checked 16:02 to 16:08. Local `main` was at `c055c1d` for the history search and moved to `79f57e7` while I worked; the value search was run again on the newer commits. The remote holds `main` (at `90625bb`) and the tag `e2e-phone-signed-1146`.

## The one blocker: a scannable link to the live app, with the enrolment code

- **What.** The decision screen draws a QR code for `PUBLIC_URL/phone/?code=…`. I decoded every tracked and untracked image (217): 20 carry a readable QR, all with today's tunnel host, and the ones I tested carry the code the live app is offering now (`GET /api/issuer/enroll-code` answers `enrolled: false`).
- **Where, tracked.** `deck/img/decision.png` (commit `b6812b5`), and so probably `deck/sign-off-deck.pdf`; `NOTES/shots-judge/01-home-5s.png`, `01b-home-full.png`, `02-walker.png`, `03-grabbar.png`, `04-chair.png`, `05-rejected-row.png`, `06-more-dearer.png`, `11-sheetpicker.png`, `12-change.png` (commit `7b3b56e`, already on the remote `main`, so in the history that goes public).
- **Where, untracked.** `NOTES/shots-walk-1542/` (9 images with the QR, 13 MB, not ignored: a `git add -A` would commit it). Now ignored by an addition to `.gitignore`.
- **What it exposes.** Not a key. It lets a stranger open the approver's page on the live app and enrol their own browser as the approver before Dana's phone does, which would take over the demo. Admin routes through the tunnel still need `SIGNOFF_ADMIN_TOKEN`, which is nowhere in the repository.
- **Smallest remedy, no history rewrite.** Any one of these before the repository is made public:
  1. Enrol Dana's real phone first (DEMO.md's checklist already asks for it). I did not verify that a second enrolment with the same code is refused once a phone is enrolled; `tests/sign/test_takeover.py` says a reset makes a new code, so check that case or use 2.
  2. Make a new code from the laptop (the reset that `test_a_reset_makes_a_new_code` covers) after the last screenshot is taken, so every image in the repository carries a dead code.
  3. Keep the repository private until the tunnel is stopped.
- **After the event.** Stop the tunnel; the address dies with it and the images are then harmless. Removing the images from the tree does not remove them from history, so removal alone is not a remedy.
- The four images I added under `docs/` carry no readable QR: in `docs/decision.png` the QR and the code are painted over.

## 1. Secrets and private data

### How it was checked

Two scripts, kept outside the repository, neither prints a value:

- **Value search.** Reads every `NAME=value` from `~/.config/tokensand.env` and `.env` (32 names in each, the same names; 29 values of 8 or more characters, also tried base64 and URL-encoded) and searches for the values in: every tracked file (1,087); every untracked file that is not ignored; `git log -p --all -m` (10.3 million lines, 659 commits on `main` plus 10 stream branches, 112 local checkpoint refs and the tag); and every object in the object database (3,566 blobs and commits, reachable or not).
- **Pattern search.** Tracked files and every added line in history, for `sk-`, `sk-ant-`, `persona_sandbox_` / `persona_production_`, `pk_`, `secret-`, `client-`, `Bearer …`, authorization and `x-api-key` headers with a value, `SIGNOFF_ADMIN_TOKEN` with a value, PEM private keys, JSON private-key fields, passwords, URLs with a user and password, GitHub and AWS key shapes, JWTs, Persona inquiry ids, `trycloudflare.com`, email addresses, phone numbers, street addresses, the builder's name, and long hex or base64 strings in `.json`, `.jsonl`, `.md`, `.txt`, `.log`.

### Result: key values

| Where | Hits |
|---|---|
| Tracked files | none (see `AIRBYTE_URL` below) |
| History, all refs | none (see `AIRBYTE_URL` below) |
| Untracked, not ignored | none |

The only value that matched anything is `AIRBYTE_URL`, at `CONTRACT.md:253`, `signoff/airbyte/ab.py:8` and `streams/AIRBYTE.md:10` (first commit `f06bb70`). It is a localhost address with no user, password or query in it, so it is not a secret. Nothing to do.

`ANTHROPIC_API_KEY`, `PERSONA_API_KEY`, `PERSONA_PRODUCTION_API_KEY`, `SENSO_API_KEY`, `SIE_API_KEY`, `SINGLESTORE_PASSWORD`, `SINGLESTORE_URL`, `COGNEE_API_KEY`, `EXA_API_KEY`, `EXA_API_KEY_BACKUP`, `ARCEE_API_KEY`, `AMPLITUDE_AI_API_KEY`, `STATSIG_SERVER_SECRET`, `STATSIG_CLIENT_KEY`, `AIRBYTE_CLIENT_SECRET`, `AIRBYTE_PASSWORD`, `SIGNOFF_ADMIN_TOKEN` and `PUBLIC_URL`: not found anywhere.

Three values are shorter than 8 characters and were not searched by value, as instructed: `AIRBYTE_EMAIL`, `SINGLESTORE_PORT`, `SINGLESTORE_USER`. The email pattern search found no personal address anywhere, so `AIRBYTE_EMAIL` is not exposed by that route either.

### Result: key formats

| Pattern | Where | What it is |
|---|---|---|
| `sk-ant-`, `sk-` | `.agents/skills/claude-api/shared/cost-optimization.md:38`, `managed-agents-tools.md:385`, and the same two under `.claude/skills/` | placeholders in vendored documentation (15 and 19 characters), not keys |
| `password=` | `signoff/airbyte/sync.py:30` | the word "staging" for a throwaway local container; the line says so |
| `SIGNOFF_ADMIN_TOKEN` with a value | `tests/sign/test_takeover.py:78`, `tests/test_app_smoke.py:17` | test-only stand-ins set with `monkeypatch`; the real value is nowhere |
| `Bearer`, authorization header, `x-api-key`, PEM private key, JSON private-key field, `persona_…`, `pk_`, `secret-`, JWT, GitHub, AWS | none | |
| Long hex or base64 in data files | 318 files, about 8,000 strings | content hashes (`payload_sha256`, `sheet_hash`, `digest`, `integrity`), store product handles, image URLs and pagination cursors from public store pages; one `sig` field, a signature, which is public by design |

### Keystore and `data/`

- `signoff/sign/_runtime/` (the keystore): ignored, never tracked, never in any commit.
- `data/egress/`, `data/receipts/`, `data/obs/`: ignored now and none is tracked. `data/obs/events.jsonl` was on `main` once (commit `f79ea69`): timing rows only (`name`, `at`, `duration_ms`, `success`, `session_id`, `sheet_id`), no headers, no keys. `data/egress/ledger.jsonl` appears only in a local checkpoint ref (`da90d27`), which a normal push does not publish; no header or key in it either.
- `demo/signer.py` generates its key at run time; no key is stored in the tree.
- No API response with an authorization header is tracked or in history.

### Privacy items (not credentials)

1. **A real Persona inquiry id** (`inq_At…`, 34 characters) at `NOTES/INTEGRATOR.md:2309` and `NOTES/REVIEW-design-1508.md:36`, on `main` since `1d00e78`. An inquiry id cannot be read without `PERSONA_API_KEY`, so it exposes nothing by itself. Smallest remedy: replace the id with `inq_…` in those two lines. It stays in history either way; acceptable. The other inquiry id, in `web/screen/fixture-signed.json:437` and `:470`, is a labelled fake.
2. **The builder's name**, besides git author metadata:
   - `LICENSE:3` and `SUBMISSION.md:29`, `CONTRACT.md:22` (the GitHub handle): expected.
   - Full name: `NOTES/INTEGRATOR.md:317` (a sponsor workspace name). First name: `NOTES/INTEGRATOR.md:1126`, `NOTES/REVIEW-everything-1500.md:158` and `:234` ("…'s Org", the Senso organisation name).
   - Home-folder paths that carry the username: `.hk/config.json:141`, `CONTRACT.md:4`, `streams/ENGINE.md:5`, `streams/MEMORY.md:43`, `streams/SCREEN.md:5`, `streams/SIGN.md:5`, `streams/STORE.md:6`, `evals/firedrill/_local/plan.json:7` and `:17`. They point at a private research folder and at worktrees that a judge cannot open. Harmless but odd; see hygiene.
   - His email address: not tracked anywhere and not in any diff. It is in git author metadata only.
3. **Two sponsor staff named** at `NOTES/INTEGRATOR.md:317` (first and last names, as people to ask in the room). They are real people who did not ask to be in a public log. Smallest remedy: reword that line to "sponsor staff".
4. **The public tunnel address.** As text, today's `PUBLIC_URL` is not in any tracked file or commit (as a QR image it is: see the blocker at the top). `trycloudflare.com` appears as the bare domain in `scripts/tunnel.sh` and `signoff/airbyte/sync.py` (no host name). One older tunnel host name is in `data/order/export_url.txt` in a local checkpoint ref only (`8966b32`); not on `main`, not on any branch, not published by a push of `main`.

Emails, phone numbers and addresses that are tracked: store customer-service lines and addresses from public product pages (`data/pool/`, `data/sheet2/`, `data/sheet3/`, `data/reviews/`), documentation examples (`jane@co.com`, `user@example.com`), two agent identities at `cognee.agent`, and the invented `14 Oak Street` in `tests/talk/`. No real private person.

### What a push publishes

The remote holds `main` and one tag. The 112 `refs/t3/…` checkpoint refs and the 10 `stream/*` branches are local. They are clean of key values too, so pushing them would not leak a key, but there is no reason to: push `main` only (`git push origin main`), not `--all` or `--mirror`.

### `.gitignore`

Covers `.env`, `.env.*` (keeps `.env.example`, which holds names only), the keystore, `data/egress/`, `data/receipts/`, `data/obs/`, `.venv/`, `__pycache__/`, `node_modules/`, `demo/out/`, `.DS_Store`, `.hk/state/`. `.pytest_cache/` ignores itself. Gaps closed by additions in this change: `*.log` outside `data/figures/` (the run logs under `data/figures/**/_runs/` are tracked on purpose and stay tracked), `.pytest_cache/` and `.ruff_cache/` stated outright, and `NOTES/shots-walk-1542/`.

### After the event

No key has to be revoked before publishing. Rotating the day's keys after the event is still sensible, since they sat in two plain files on a laptop that ran a public tunnel all day: `SIGNOFF_ADMIN_TOKEN` and `PERSONA_PRODUCTION_API_KEY` first.

## 2. First impression

**README.md, changed:**
- Added four screenshots under `docs/` and a two-by-two table of them after "What it does": `decision.png` (233 KB, live app, 1440 x 810, QR and code painted over), `replay-last.png` (181 KB, live app, the overlay after it played to the end, 11 of 11), `seal-changed.png` (173 KB, copied from the verify folder's `seal-fail.png`), `phone-sign.png` (149 KB, copied from the tracked `evals/phone_screens/sheet4/10-sign-before-first-tap.png`). All under 600 KB. The live shots were taken with every non-GET request blocked in the browser; none was attempted.
- Added one line above the run block: it needs `uv`.

**Why the phone image is a copy:** a fresh browser on `/phone/` shows the enrolment screen, not Sign, and reaching Sign means enrolling, which is a POST. The copied image is the same sign screen from an earlier run today.

**Claims checked and found true:** 91 pages, 152 options (61 pass, 48 fail, 9 unclear, 34 not stated) match `GET /api/state` `counts` exactly; three stores; "a disagreement blocks" matches `two_readers.mode`; P-256 and SHA-256 match `/seal/`; replay mode says so in the top bar ("replay of cached store data"); the people are marked invented in the state and on screen. The README says "states" and never "proves".

**Left for the integrator, I could not fix them:**
1. `README.md:5` still reads `[Demo video](<link>)`. A judge sees a dead link in the first screen. Put the URL in or remove the line.
2. The decision screen says "3 models agree" beside a quote; the README names two readers (Claude Sonnet, and Qwen on SIE) and `data/figures/_runs/` has a third (`sie-urchade-gliner-multi-v2.1`). Either name the third in "How it works" or leave it; the screen and the README currently differ by one.

**"Run it" on a fresh clone: works as written.** `git clone` to a temp folder (no `.env`), `uv sync`, then the README's line on port 8048, with `HOME` pointed at an empty folder so `~/.config/tokensand.env` could not supply keys. `/` answered 200 after 5 seconds; `/api/state` said `mode: replay`, `sheet4`; `/phone/`, `/seal/`, `/trail/`, `/graph/` all 200. The temp clone and its server are gone.

**Code note for the integrator (not changed):** `signoff/config.py:8` to `:12` loads `~/.config/tokensand.env` before the checkout's `.env`. On this laptop a "fresh clone without keys" therefore still has every key. It does not matter to a judge, who has no such file, but a test of replay-without-keys on this machine only means something with `HOME` moved, as above.

## 3. Hygiene (report only; nothing deleted)

**Size.** `.git` is 111 MB. Tracked files: 1,090 or so, 50 MB in the tree, of which PNGs are 18.7 MB (121 files).

| Tracked | Size | Recommendation |
|---|---|---|
| `NOTES/shots-judge/` (26 PNG) | 4.4 MB | Remove from the tree (`git rm -r`): review screenshots, 9 of them with the live QR. Not referenced by the README. |
| `NOTES/INTEGRATOR.md` | 403 KB, 2,300+ lines | Internal log. It carries a real Persona inquiry id (line 2309), the builder's full name and two sponsor staff names (line 317). Either fix those two lines or remove the file from the tree. |
| `NOTES/relay-shots/` (3 PNG) | 0.2 MB | Fine to keep or remove. |
| `data/figures/**/_runs/` (`read_ledger.jsonl` 1.2 MB, 0.8 MB, 0.7 MB; 54 `.log` files) | 9.7 MB with the rest of `data/figures` | Keep: they are the evidence behind "Measured". Odd-looking only because of the `.log` names. |
| `deck/sign-off-deck.pdf`, `deck/img/decision.png` | 785 KB, 546 KB | Keep the deck; `deck/img/decision.png` carries the live QR (see the blocker). |
| `.agents/skills/` and `.claude/skills/` | 2.0 MB each, 103 files each, identical copies of a vendored skill | A judge will find two copies of someone else's documentation odd. Remove one (or both) from the tree; `skills-lock.json` records what they were. |
| `web/trail/`, `web/graph/shots/`, `web/seal/shots/`, `evals/phone_screens/` | 3.6, about 2, about 2, about 3.5 MB | Screenshots kept beside the pages. Harmless; removable if size matters. |
| `uv.lock` | 532 KB | Keep. |
| `evals/firedrill/_local/` (`plan.json`, `state_log.jsonl`, `campaign2.txt`, `descriptor.json`) | small | Local run state with laptop paths (`plan.json:7`, `:17`). Remove from the tree and ignore `_local/`. |

No `.DS_Store`, no `__pycache__`, no `.pytest_cache`, no video or audio recording is tracked. `demo/out/` is ignored.

**Untracked, not ignored:** `NOTES/REVIEW-walk-1542.md` (fine to commit) and `NOTES/shots-walk-1542/` (13 MB, live QR; now ignored). `NOTES/shots-design-1508/` (81 MB) was already ignored.

**Odd at the top level for a judge:** `AGENTS.md`, `CLAUDE.md` (11 bytes), `CONTRACT.md` (49 KB), `OPEN.md` (24 KB), `DEMO.md`, `SUBMISSION.md`, `streams/`, `hk`, `.hk/`, `skills-lock.json`: working files of the build, some pointing at paths on the builder's laptop (`CONTRACT.md:4`, `streams/*.md`, `.hk/config.json:141`). Not harmful. If there is a minute, one README line under "Built today" saying that `CONTRACT.md`, `streams/` and `NOTES/` are the day's working notes turns them from clutter into evidence.

**`./hk submit` (run 16:04): 4 things to fix.**
- FAIL Repository URL: HTTP 404, because the repository is still private. Clears when it is made public.
- FAIL Demo video URL: empty.
- FAIL Team: empty.
- FAIL secrets: "key-shaped string" at `data/sheet3/pool/raw/mrpen.com/kids_headphones.json:915` and `:916`. A false alarm: the checker's `sk-` pattern matches the middle of a store product handle (`…de`**`sk-toy-…`**, "desk toy"). It is a product URL, not a key. It will keep failing until the pattern requires a word boundary before `sk-` in `scripts/hk/submit_check.py:26`; that is a kit fix, not made here.
- WARN working tree: uncommitted changes (mine: `README.md`, `.gitignore`, `docs/`, this file).
- Everything else passes, including "pushed: HEAD is on the remote".

## Files I changed

`README.md` (screenshots table, the `uv` line), `.gitignore` (additions only), new `docs/decision.png`, `docs/replay-last.png`, `docs/seal-changed.png`, `docs/phone-sign.png`, and this report. Nothing committed, nothing pushed, no POST to the live app.
