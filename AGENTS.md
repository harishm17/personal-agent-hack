# Agent rules for this hackathon repo

Timed build. Every agent (Claude Code, Codex, Cursor, Gemini CLI) working here follows these rules.
The kit's hooks show the clock on every prompt; plan your work against it.

## Hackathon mode (overrides general workflow skills)
- Setup is the `hackathon-kickoff` skill. It replaces brainstorming and long plans: no per-task design docs,
  no spec review loops. If the brief is clear, build.
- In a stream checkout, follow the `hackathon-stream` skill. At a sync point or freeze, the integrator follows
  `hackathon-integrate`. For the product's checks and evals, use `hackathon-verify-loop`. From feature freeze on,
  use `hackathon-demo`.
- Still applies: verify before claiming done (show the command and its output), and debug systematically
  when stuck for more than 10 minutes.
- Tests: write them for the verifier, the scoring code and anything the demo depends on. Skip test-first for
  UI and glue code.

## Hard rules
- CONTRACT.md is the source of truth for interfaces, file formats, ownership and the timetable. If code and
  contract disagree, the contract wins until the integrator amends it.
- Edit only the paths your stream owns. Requests to other owners go in `NOTES/<OWNER>.md` (append only).
- Commit small and often to your own branch, staging only your own paths (`git add <your paths>`), never `-A`.
- No AI or tool authorship lines anywhere: no Co-Authored-By trailers, no "generated with" notes in commits,
  PRs, docs or code.
- Secrets live in `.env` (gitignored). Never print, log or commit them.
- Numbers shown in the demo or README come from code or `./hk eval`, never from a model's guess.

## Commands
`./hk help` lists everything. Common: `./hk status`, `./hk check`, `./hk eval`, `./hk record`.

## Quirks log (append only)
One 1–3 line entry per non-obvious setup or build quirk, prefixed with your stream name, so nobody hits it twice.
Model and API facts that differ from training data go here too (exact model IDs, parameter traps, limits).

- INTEGRATOR 11:05: keys are read by `signoff/config.py` from `~/.config/tokensand.env` and then `.env`. A worktree has no `.env`; that is fine. Use `config.env("NAME")`, never print a value.
- INTEGRATOR 11:05: Python is pinned to 3.14 (`.python-version`). Run everything with `uv run`. Ports: main 8800 (the tunnel; 8000 is taken by another program on this Mac), ENGINE 8001, STORE 8002, SCREEN 8003, SIGN 8004.
- INTEGRATOR 11:05: stores accept a call only with `meta["ucp-agent"].profile` set to a public https URL of `profile/agent-v1.json` served with `Cache-Control`. A changed profile needs a new file name (stores cache it). Prices are in cents. Never call a checkout tool.
- INTEGRATOR 11:05: SingleStore password contains `=;(^[`; pass host, user and password as separate arguments, or use the URL-encoded `SINGLESTORE_URL`.
- INTEGRATOR 11:05: Node is 26.13.1 (Firedrill needs 26.13.1 or newer). Codex is not installed, so cross-check uses a fresh Sonnet session.
- INTEGRATOR 11:05: current Claude model IDs: `claude-fable-5-2`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`. Use the `claude-api` skill before writing an API call.
- INTEGRATOR 11:27: a test that calls a real outside service (SingleStore, a store, a model) gets `@pytest.mark.live`. The gate runs `-m 'not live'` (set in pyproject.toml) and must stay under 60 seconds; run live tests yourself with `uv run pytest -m live`. Live tests on the shared database must use their own table names so two streams cannot collide.
- STORE 11:30: a store's `create_cart` reply is top-level (`id`, `totals`, `continue_url`), not nested under "cart"; Shopify cart ids contain "?key=".
- SIGN 11:30: Senso `POST /org/evals/text` gives no verdict on claims about another brand (a store), with `author` set to `ai_assistant` or `organization`: they come back `about_brand: false`, `bucket: "general"`, unscored. Senso checks the sheet against the therapist's order and the handout; store sentences are checked by span match in code.
- ENGINE 11:21: the Arcee key lists models but every completion returns 402 until the account has credits.
- ENGINE 11:30: SIE has an OpenAI-compatible chat endpoint, https://api.superlinked.com/v1/chat/completions, Bearer SIE_API_KEY; Qwen/Qwen3.8-27B-FP8 answered warm in under 1 s. Usage carries credits_charged.
- ENGINE 11:30: `claude -p` for batch work: run it outside the repo with --tools "" --strict-mcp-config --setting-sources "" --no-session-persistence, or the repo's hooks run on every call. About 3 s per call; --model claude-sonnet-5-5 works.
- SIGN 11:50: Senso's judge is not steady on bare statements; prefix with "Our order requires" and put the same sentence verbatim in the document; a wait:true call can return 202 "queued" under load, poll /org/evals/runs/{id}.
- INTEGRATOR 11:40: ANTHROPIC_API_KEY is in the keys file with about $4.50 of credit. Batch reads never use it; live calls only, capped per process.
- INTEGRATOR 12:20, the builder's rule: avoid overfitting instructions and fallbacks. When something fails, enforce the general property that was violated, in code, not a special case for the example that failed: no lists of formats, no prompt lines aimed at one product or pattern. Add a fallback only where the live demo truly needs one, and make it visible and labelled; never a silent one.
- INTEGRATOR 12:20: routes that reset the app, switch the reader, reload data or act as the shopper answer only to the laptop (or with header X-Admin-Token = SIGNOFF_ADMIN_TOKEN); through the tunnel they return 403 `local_only`. The guard is in signoff/app.py (`LOCAL_ONLY`); tell the integrator if you add such a route.
