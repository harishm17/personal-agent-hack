# Submission draft

<!-- The form at tokensand.com/personalagenthack/submit keeps its draft only in the browser tab, so the
     answers live here. `./hk submit` checks this file and the repo. It can be edited after the first submit. -->

## Project name (required, max 140)
Sign-Off

## One-sentence description (required, max 300)
A shopping agent that buys under someone else's limits and signature: the person who knows sets limits the shopper cannot edit, the store's own words decide each line, and the cart exists only when that person signs.

## Project description (required, max 1500)
Sign-Off shops real stores to a list that someone else wrote and must sign. Priya needs four bathroom fixtures. Marco, the plumber who installs them, wrote the list: a toilet with a 10 in rough-in and at most 1.28 gpf, a faucet at most 1.2 gpm, a shower head at most 1.8 gpm, a vanity at most 30 in wide. The agent searches four real stores and reads every product page. A figure counts only when code finds its exact quote in the store's text; code, not the model, compares it with the limit. Priya cannot change a limit. Marco can, from his phone. Carts are created at the stores only after he signs; nothing is checked out [check: sheet 2 end to end]. Senso holds Marco's order and checks each sentence of the sheet against it; a conflict blocks the signature. SingleStore holds products, figures, limits and every decision; one SQL statement returns what passes. Superlinked SIE runs two small open readers on the same pages; a Statsig gate picks which reader decides, and Amplitude records each tool call. Persona checks the signer in sandbox [check]. A local Airbyte sync delivers the store records [check]. The people are invented; the stores, text, prices and carts are real.

## Tools and sponsors used (required)
Senso
SingleStore
Superlinked SIE
Statsig
Amplitude
Persona
Airbyte
<remove any line whose [check] above is not true at 15:30; Firedrill only if a campaign ran>

## Repository URL (required, url)
https://github.com/harishm17/personal-agent-hack

## Demo video URL (required, url)
<a link that opens while logged out>

## Live app URL (optional, url)

## Team (required)
<team size; full name and email for each member>

## Judge access notes (optional, max 6000)

## Technical architecture (optional, max 1200)
A FastAPI engine with plain JavaScript screens: the shopper's view, the signer's phone, and the trail. A reading model with no tools proposes a figure, unit and quote; code locates the quote and applies one number rule to every reader (Claude Sonnet, and Qwen and GLiNER on SIE). A Statsig gate, polled every 3 seconds, switches the deciding reader until signing. The limit test runs in code and as one SingleStore statement over pool, figures, limits and strikes. Records: a decisions table per state version, hash-chained receipts, and a ledger of every payload sent out. The phone signs each request against the sheet hash; Senso's check gates the signature, then carts are created. Airbyte Core in Docker moves files into MySQL staging, which our code copies to SingleStore.

## Setup instructions (optional, max 1200)

## Lessons learned (optional, max 1200)

## Project screenshot (optional)
<file path, under 5 MB>
