# Submission draft

<!-- The form at tokensand.com/personalagenthack/submit keeps its draft only in the browser tab, so the
     answers live here. `./hk submit` checks this file and the repo. It can be edited after the first submit.
     Rewritten 15:30 from NOTES/REVIEW-everything-1500.md section 3; [check] marks what is settled at 15:42. -->

## Project name (required, max 140)
Sign-Off

## One-sentence description (required, max 300)
A shopping agent that works under someone else's signature: a therapist writes what a patient's home needs, the agent keeps a store's figure only as an exact quote that code can find, code compares it with her limits, and carts exist at the real stores only after she signs from her phone.

## Project description (required, max 1500)
What it is. Sign-Off shops real stores to an order someone else wrote and must sign. Invented example: Rosa comes home after a hip replacement. Dana, her therapist, wrote the order: each item must hold 300 lb and fit the tub or the door. Her daughter Elena's agent shops.

How it works. The agent read 91 product pages at three real stores. A figure counts only when code finds its exact quote on the store's page; code compares it with the limit; nothing is bought on a guess. Elena cannot change a limit: she asks, and Dana decides on her phone. Dana signs one fingerprint over the limits, measurements, quotes, picks and prices; one changed value fails the check. Carts are created only then. Nothing is checked out.

Where each tool is used.
Senso: holds Dana's order and checks the sheet's sentences against it before she signs.
SingleStore: products, figures and decisions; the limit test as one SQL statement; memory and its vectors.
Superlinked: second reader of every page; the guard on messages to stores' agents; memory embeddings.
Statsig: gate on "both readers must agree", measured, not adopted.
Amplitude: the agent's tool-call events.
Airbyte: local sync of store records into the database.
Firedrill: a simulated shopper attacking the refusal.
Cognee: the run's knowledge graph, one dataset per owner.
Persona: sandbox identity check before the signature.

People and messages are invented. Stores, pages, prices and carts are real.

## Tools and sponsors used (required)
Senso
SingleStore
Superlinked SIE
Statsig
Amplitude
Airbyte
Firedrill
Cognee
Persona
<[check] at 15:42: Amplitude only with the delivered count known; Persona only if a sandbox inquiry ran on the submitted build. Not sponsors: Anthropic Claude (the reference reader), Exa (review search).>

## Repository URL (required, url)
https://github.com/harishm17/personal-agent-hack

## Demo video URL (required, url)
<a link that opens while logged out>

## Live app URL (optional, url)

## Team (required)
<team size; full name and email for each member>

## Judge access notes (optional, max 6000)
Everything about the people is invented: Dana, Elena, Rosa, the order and every message. The stores (carex.com, vivehealth.com, parentgiving.com), their product pages, prices and carts are real. Nothing is paid for or checked out; the client never calls a checkout tool.
To look without keys: start the replay (see Setup) and open / (the shopper's screen), /seal/ (what the signature covers; change one value and the check fails; real attempts to get a cart without the approver are refused), /phone/ (the approver), /trail/ (each step as a record) and /graph/ (the run as a graph).
What to try: on the decision screen, "Replay the run" shows how the agent got to the list; "Ask Dana" under a limit sends the approver a request, because the shopper's side cannot change a limit. On /seal/, click any value.
Known limits: store pages were fetched once on the day and read by two models, not by a person. The identity check is Persona's sandbox and checks nobody. No store checks the signature. The guard on outgoing messages uses a small model to find names and health details and stops some messages it need not.

## Technical architecture (optional, max 1200)
A FastAPI engine with plain JavaScript pages: the shopper's screen, the approver's phone, the trail, the signature page. A reading model with no tools gets one store page and the names of the figures and proposes a figure, unit and quote; code finds the quote in the page and applies one set of number rules to every reader (Claude Sonnet, and Qwen on Superlinked SIE; a disagreement makes the product unclear). Limits are read from the written order with their sentence quoted, compared in code and again in one SingleStore statement. Stores are reached over their own MCP endpoints: search, product details, ask the store's agent, create cart. Records: a decision per candidate and state version, hash-chained receipts, a ledger of every outbound payload. The phone holds an ECDSA P-256 key; each request is signed against the SHA-256 fingerprint of the canonical sheet. Senso checks the sheet's sentences against the order document before signing; a Persona sandbox inquiry gates it; carts are then created for the signed picks only. A Statsig gate switches the two-reader rule. Memory rows carry an owner and the receipt that made them (SingleStore, SIE embeddings, Cognee datasets per owner).

## Setup instructions (optional, max 1200)
Needs Python 3.12+ and uv.
uv sync
SIGNOFF_MODE=replay SIGNOFF_SHEET=sheet4 uv run uvicorn signoff.app:app --port 8800
Open http://localhost:8800 for the shopper's screen and http://localhost:8800/phone/ for the approver. Replay mode uses the store data saved on the day and says so in the top bar. Live mode needs the keys named in .env.example.

## Lessons learned (optional, max 1200)
The strict rule was the wrong default. Requiring two readers to agree on every figure caught five misreads and blocked twenty-seven figures that only one reader found; we measured it behind a gate and kept "a disagreement blocks" instead.
"Unclear" had to be its own answer. A page that sells an 18 inch option and describes only 12, 16 and 24 is neither a pass nor a fail, and saying so is more useful than guessing.
A signature over a cart covers very little. Putting the limits, the quotes and the ordering under it is what lets a second person answer for a purchase she did not make.
A guard that finds names with a model stops too much: it took "I" for a person. Values from the order are caught exactly; free text is not.
We added more than one demo can carry. The parts that survived are the ones that answer "who is allowed to decide".

## Project screenshot (optional)
<`/seal/` after a signed run, under 5 MB>
