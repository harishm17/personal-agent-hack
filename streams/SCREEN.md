# Stream SCREEN

You are the SCREEN stream at a timed hackathon (deadline 16:30 today). Use the hackathon-stream skill.
First run `./hk own SCREEN`. Then read CONTRACT.md and the AGENTS.md quirks log. Then read, in this order:
- `/Users/harishm/research/2026-11-20-tokensand-personal-agents-hackathon/IDEA.md`, section "The screen:
  what it knew, what it decided, and why" (this is your spec; visualising the context and how each decision
  was made is the builder's first priority);
- `.../research/mock/sign-off-screen-v2.png` and `.html` beside it (a design picture with placeholder data;
  write the screen fresh, do not copy the file);
- `.../research/panel9-screen-review.md` (what the review asked for).

## You own
`web/screen/**`, `demo/**`, `tests/screen/**`. Everything else: request changes in `NOTES/<OWNER>.md`.
Develop on port 8003: `uv run uvicorn signoff.app:app --port 8003` serves `web/screen/index.html` at `/`
and the fixture run at `/api/state` from the first minute. No build step: plain HTML, CSS, ES modules, SVG.

## Build, in this order (by 13:10)
1. **The line view: the checks as sums, each term owned.** One row per limit, drawn from
   `candidates[picked].checks[].terms`, `op`, `bound`, `margin`. Blue: the shopper stated it. Amber: the
   store's own words. Violet: the issuer set it. Every coloured number carries the owner's name in text.
   The tightest margin is always shown, including "nothing to spare". Then the store's sentence for the
   chosen product with the figure highlighted (from `quote`, `start`, `end`) and a link to the page.
2. **The candidates against the limit.** Every candidate of the line plotted; the issuer's limit is a
   violet wall that moves when `/api/state` changes; dots outside go grey; the picked dot has a blue ring;
   a dashed gutter holds products whose page never states the figure. Start with a single strip, then the
   two-limit passing box (the two limits with store figures; x one, y the other). "Why this one" from
   `why`. Redraw on every `GET /api/events` message by refetching `/api/state`; transitions under 300 ms.
3. **The sheet strip and the seal.** Six tiles in a plain grid, each with status and tightest check; a
   tile opens its line. The seal: "Not signed. No cart exists at any store."; after signing: signer, time,
   sheet hash, the real cart links, the Persona inquiry id. A badge shows `mode` when it is `fixture` or
   `replay`. Invented people are labelled "invented" in words.
4. Elena's controls: her measurements (`POST /api/shopper/fact`) and a small box to talk to the agent
   (`POST /api/shopper/say`, shows the refusal).
5. After 13:10: fact chips that travel into the sum, the counts strip (`counts`), the arrival band, cost
   to undo (`undo`), Senso's verdicts (`senso`), the SingleStore query panel
   (`GET /api/sql/passing-box?line_id=`), sheet 2. Cut first: motion, the arrival band, sheet 2.

## Rules for a projector
Build on a 960 x 540 canvas shown at 200%: nothing under 16 px, numerals in the sums 44 px, bars and dots
at least 20 px, one focal point per demo beat. Dashed grey means one thing only: not known or not stated.
Wording: "the model reads the figure; code checks that the quote is in the store's text and does the
sums". "states", never "proves". Run the `web-design-guidelines` skill once before 13:10.

## Interfaces you consume
`GET /api/state` (shape of `fixtures/state.json`; new keys may appear, none are renamed), `GET /api/events`,
`POST /api/shopper/fact`, `POST /api/shopper/say`. Until the ENGINE stream is merged, moving a limit can be
simulated in the page behind `?sim=1` (clearly marked) so the motion is built against something.

## Done when
`uv run -q pytest -q -x` is green; a screenshot of `/` at 1920 x 1080 shows the L2 line with both sums, the
plot with nine dots, the store's sentence, six tiles and the seal, all drawn from `/api/state`. Take the
screenshot yourself and look at it before saying done.

## Sync points
12:20 first sync (real data replaces the fixture) · 13:10 end-to-end run · 15:00 feature freeze ·
15:30 code freeze. No AI or tool authorship lines in commits, docs or code. Commit to `stream/SCREEN`.
