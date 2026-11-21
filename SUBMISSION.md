# Submission draft

<!-- The form at tokensand.com/personalagenthack/submit keeps its draft only in the browser tab, so the
     answers live here. `./hk submit` checks this file and the repo. It can be edited after the first submit.
     Rewritten 15:30 from NOTES/REVIEW-everything-1500.md section 3; [check] marks what is settled at 15:42. -->

## Project name (required, max 140)
Sign-Off

## One-sentence description (required, max 300)
A shopping agent that works under someone else's signature: a therapist writes what a patient's home needs, the agent keeps a store's figure only as an exact quote that code can find, code compares it with her limits, and carts exist at the real stores only after she signs from her phone.

## Project description (required, max 1500)
The problem. The person who knows what is right to buy is often not the one buying. Invented example: Rosa comes home after a hip replacement. Dana, her therapist, wrote what the house needs. Her daughter Elena shops with an agent.

What it does. The agent buys only what Dana's order allows, and only after Dana signs.

How it works.
1. Dana's limits come from her order, such as "must hold 300 lb".
2. The agent searches three real stores and reads all 91 product pages. It must quote the exact words where the store states each figure, and code checks the quote is on the page.
3. Code, not the model, compares the figure with the limit. If a page does not state it, nothing is bought on a guess.
4. Elena cannot change a limit. She can ask; Dana decides on her phone.
5. Dana signs on her phone. The signature covers every limit, measurement, quote, pick and price, so any later change fails the check.
6. Only then are carts created. Nothing is checked out.

Tools.
Senso: checks the sheet against Dana's order before she signs.
SingleStore: records, memory, the limit test in SQL.
Superlinked SIE, three models: Qwen re-reads all pages; GLiNER guards messages to stores; Qwen embeddings for memory.
Statsig: gated a stricter rule, measured.
Amplitude: agent tool-call events.
Airbyte: syncs store records.
Firedrill: simulated shopper attacks.
Cognee: knowledge graph per owner.
Persona: sandbox identity check before signing.

People are invented. Stores, pages and prices are real.

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
https://drive.google.com/file/d/1jaXve6-VmpkpN8dDHf_cIZa50rg27KWv/view?usp=sharing

## Live app URL (optional, url)

## Team (required)
<team size; full name and email for each member>

## Judge access notes (optional, max 6000)
Everything about the people is invented: Dana, Elena, Rosa, the order and every message. The stores (carex.com, vivehealth.com, parentgiving.com), their product pages, prices and carts are real. Nothing is paid for or checked out; the client never calls a checkout tool.
To look without keys: start the replay (see Setup) and open / (the shopper's screen), /seal/ (what the signature covers; change one value and the check fails; real attempts to get a cart without the approver are refused), /phone/ (the approver), /trail/ (each step as a record) and /graph/ (the run as a graph).
What to try: on the decision screen, "Replay the run" shows how the agent got to the list; "Ask Dana" under a limit sends the approver a request, because the shopper's side cannot change a limit. On /seal/, click any value.
Known limits: store pages were fetched once on the day and read by two models, not by a person. The identity check is Persona's sandbox and checks nobody. No store checks the signature. The guard on outgoing messages uses a small model to find names and health details and stops some messages it need not.

## Technical architecture (optional, max 1200)
Superlinked SIE does three jobs. (1) Second reader: Qwen3.8-27B read the same 197 store pages as Claude Sonnet (666 statements); where the two read a figure differently (5 cases) the product is marked unclear and is not bought. (2) Guard: before our agent messages a store's own agent, Qwen writes the message and GLiNER finds names, health details, limits and measurements in it; code removes them or stops the message (4 of 13 were stopped). (3) Memory: Qwen3-Embedding-4B embeds each memory; SingleStore ranks them by vector for recall.
Engine: FastAPI with plain JavaScript pages. A reading model with no tools proposes a figure, unit and quote; code finds the quote on the page and compares it with the limit, in code and again in one SingleStore statement. Stores are reached over their own MCP endpoints. The phone holds an ECDSA P-256 key and signs the SHA-256 fingerprint of the canonical sheet; Senso checks the sheet against the order document first; a Persona sandbox inquiry gates signing; carts are created for the signed picks only. Statsig gates the two-reader rule. Cognee holds the knowledge graph, a dataset per owner.

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
