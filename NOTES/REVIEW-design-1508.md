# Design review, captured from 15:08

Complete. Method: Chrome through Playwright. Live instance `localhost:8800` with every non-GET request aborted
in the browser (the pages attempted none). Write states (ordering, Ask Dana, the home slider, phone enrol, limit
slider, sign, signed pages, refused attempts, the second list) on private replay copies of merged main
(`fca161c`) on ports 8034 and 8035; the worktree is removed. Sizes: 1440 x 810; 960 x 540 at 1.5 device pixels
(150% zoom); 390 x 844 for the phone. 467 shots in `NOTES/shots-design-1508/` (`phone-contact-1..3.png` are contact sheets of the phone states), named
`<page>-<nn>-<state>@<1440|150|phone>.png`; `w-`, `x-` and `refusal-` were taken on the copies.
Not done: the chat box was typed into but not sent (it calls a model); a strike was opened but not confirmed;
the Persona and Relay links were not opened. Side effects of the copies, which read the shared keys: pressing "check identity" on each copy started one Persona sandbox inquiry (two in all), and each copy ran the Senso check on its own sheet. Nothing was written to the live instance. On my copy I left the shower-chair limit at 600 lb before signing, so
the signed shots show "nothing passes" for that item and a total of $72.70: a real state, not the demo's.

S = under 10 minutes, M = 10 to 25, L = more.

## Verdict

- **Best looking: `/seal/`.** One idea per region, one state change (ink to red) that reads from the back, and the
  only page whose layout reflows properly at 150%. `/` is a close second at 1440.
- **Weakest: `/graph/`, "The run" view.** Rows of unlabelled circles, 41 strings at 10 px, 26 boxes at stage 2.
  This is the pattern already rejected ("abstract dots").
- **Do not show:** Memory "The run" (show "The decision" view or skip the page); an opened row of the Tools
  drawer; Trail's "What left" matrix; Trail on the second list (its guard row is three empty boxes). Do not
  present at 150% zoom: `/` and `/graph/` break (T1).

## The ten that matter most, as seen from the back of the room

| # | What | Where | Fix | Size | Owner |
|---|---|---|---|---|---|
| T1 | **150% zoom breaks two pages.** `/`: the Recommended row is cut in half by the bottom edge, the Signature card is off screen, "Total $114.69" loses its last digit. `/graph/`: nodes sit on top of one another, the stage and the right panel are clipped, the bar's total is cut to "$" | `screen-01-shower-chair@150.png`, `graph-01-default@150.png` | Present at 100% full screen (125% at most). Code: D1 to D3 below; graph: the run view's fixed node widths do not fit a 960 px window, so under 1180 px wide show the decision view instead | S / M | `web/screen`, `web/graph` |
| T2 | **The top bar is different on every page**, so it jumps on each navigation. `/`: brand, title, tabs, "invented people, real stores", Tools at work, pill, "Total $114.69". Trail: brand, **tabs, then title**, "3 items · invented", pill, "$114.69" with no label. Memory: title then tabs, "3 items · invented people, real stores", no label on the total. Signature: "invented people", pill, **no total**. Conversations: "8 with the stores' own agents", pill says **"31 withheld"** instead of Not signed, no total | all `*-01-default@1440.png` | One order everywhere: brand · title · tabs · meta · (grow) · pill Not signed/Signed · "Total $114.69". Trail: move `.sheet` before `.tabs`. Trail and Memory: add the word "Total". Signature and Conversations: add the total; Conversations: keep the Not signed pill and put "31 withheld" in the band | S each | all five |
| T3 | **Each page opens on a different item.** `/` and Trail: shower chair. Memory: **walker**. Conversations: **grab bar** (the last thread) | `graph-01-default`, `talk-01-default` | Open on the first line of the sheet everywhere (`line = params.get("line_id") || sheet.lines[0].id`; first thread, not last) | S | `web/graph`, `web/talk` |
| T4 | **The code-matching moment does not match.** Laptop `/seal/` shows `3ac9 4ba1 dd01` and says "Dana's phone will show the same code". The phone shows 64 unbroken hex characters in 12 px grey; the signed card on `/` shows `d4d609db2348` with no spaces | `phone-contact-3.png`, `w-screen-41-signed@1440.png` | Phone `.hash`: show the first 12 characters grouped in fours, `font: 600 20px/28px ui-monospace; color: var(--t1)`, rest hidden. `/` signed card: same grouping. Replace the green sentence with "✓ same code as the laptop" | S | `web/phone`, `web/screen` |
| T5 | **`/` column header is four lines of which two are 11 px grey** ("Dana's limit · phone only", "Ask Dana"); the header row is 84 px tall and ragged | `screen-01-shower-chair@1440.png` | D4 | S | `web/screen` |
| T6 | **Memory "The run" is dots.** "stated by the stores": 60 identical circles each with two 3 px dots; "41 more that pass": a 3 x 14 grid of circles; outcome groups of grey circles with 3 px red and green dots | `graph-10-stage-05@1440.png`, `graph-01-default@1440.png` | Make "The decision" the default view (`view = params.get("view") === "run" ? "explore" : "detail"`); it is clean and reads left to right (`graph-31-decision-shower-chair@1440.png`) | S | `web/graph` |
| T7 | **One thing, several names** (table "Names" below): limit / rule / order / prescribed; unclear / refused; Recommended / the pick / cheapest that passes / cheapest that meets the order; Elena / the shopper; "Shower chair" / "shower chair"; "28 in" / "28.0 in"; Picked "$41.99" / "3 items · $114.69" | every page | Use the left column of the Names table | S each | all |
| T8 | **Internal ids on stage**: `tub_inside_width` (Trail memory shelf); "Default Title" (Signature, phone); `sign_sheet · no signature`, `set_limit L1.capacity 300 → 250 lb`, `seq 1795216182497`, "401 unsigned" (Signature); `inq_At7PFzGZjK4sjnXcJs1jJz3iB5h52n` and "Dana (self-declared)" (phone, signed); "replay" beside each cart; "USD"; `17 <= 24` (phone) | `trail-01-default`, `x-seal-unsigned-13-attempts-after`, `phone-contact-1/3` | Per page below (R6, S2, S3, P3 to P6) | S each | `web/trail`, `web/seal`, `web/phone` |
| T9 | **Trail: the rail names do not match what appears.** While the rail reads "Therapist signs" the guard row draws; at "Carts" the memory shelf draws. For the first 18 of 24 s the lower 40% of the frame is two captions over white. Pressing Play scrolls the page 16 px so the card touches the bar | `trail-31-play-f02/f12/f17@1440.png` | Rail labels for steps 6 and 7 in the replay: "Asked the store" and "Remembered" (the signature is not replayed here); `scrollIntoView({ block: "nearest" })` instead of start; R1 to R3 | M | `web/trail` |
| T10 | **"Best reviewed" recommends a 3.9 above a 4.8** and says "Cheapest that passes; none of them has a quoted rating" while ratings are printed on three rows; rating formats differ ("3.9 · 28 reviews · amazon.com", "5/5 · 2 reviews · parentgiving.com", "4.8/5 · target.com"); the walker jumps to $119.99 and the total to $189.97 with no word why | `w-screen-02-ordering-1-f02@1440.png` | Do not press the ordering control on stage. If it must work: one rating format "★ 4.8 (12)", and the reason line must name the rule actually applied | M | `web/screen` |

Next five: D5 (Why panel cut mid-sentence), D6 (Signature headline orphan), C1 (Conversations: whole paragraphs
in bold yellow), R4 ("s̶t̶o̶p̶p̶e̶d̶ 6" reads as not stopped), S1 ("without her").

## Names: one word for one thing

| Use | Now also called | Where |
|---|---|---|
| **limit** ("Dana's limit") | "Dana's rule" (Signature rows), "The rule" (Memory column), "prescribed by Dana" (Memory), "the order" (list caption, phone "from the order") | `web/seal`, `web/graph` |
| **unclear** | "refused · no unit stated" in red (Trail) for the row `/` shows grey as "✕ unclear · no unit stated" | `web/trail` |
| **Recommended** | "the pick" (Memory, Signature "pick"), "Cheapest that passes" (`/` Why), "cheapest that meets the order" (Trail, Signature, phone), "Pick now:" (phone) | all |
| **Elena** | "The shopper measured…" (Trail shelf), "the shopper asked" (Conversations list), "Each store's / Elena's" are fine | `web/trail`, `web/talk` |
| **Shower chair** (capital) | "shower chair" (Signature, phone, Trail title "Home after surgery · shower chair", Memory nodes) | `web/seal`, `web/phone`, `web/trail` |
| **28 in, 16 in** | "28.0 in", "16.0 in", "24.0 in" (Signature) | `web/seal` |
| **Picked · 3 items · $114.69** | "Picked $41.99" (`/`), "Checked 34 rejected, with reasons" (`/`) against "Checked 61 pass" (Trail) | `web/screen`, `web/trail` |
| **Therapist signs · from the phone** / **Carts · none exist yet** | "not signed" / "none exist" (Trail rail), "Dana signs from the phone · not signed · no cart exists" (Trail), "Nothing is signed yet: no cart can exist" (Signature) | `web/trail` |
| **SingleStore, Senso, Amplitude, Statsig** | "singlestore", "senso", "amplitude", "statsig" (Trail matrix) | `web/trail` |

Owner colours are the same on every page (purple Dana, blue Elena, amber store) and always 6 px dots: good.
The pick is indigo on `/` and an ink outline on Trail, Memory and Signature: acceptable, but it means indigo
appears on one page only. Pill-shaped things use four radii: 10 px (`.pill`), 12 px (Memory chips, Trail
`.fchip`, Signature), 14 px (Conversations band, Trail tokens), 6 px (`.seg` buttons): set all to `999px`.
Type: 11 to 16 combinations per desktop page; 10 px on Memory (41 strings) and Conversations (carets), 11 px on
`/` and Trail, weight 700 on Trail only (`14px/700`, 2 strings): the outliers to remove.

## `/` Decision (owner `web/screen`)

What the eye lands on first at 1440: the indigo "Recommended" pill, then the yellow figures in the left list.
That is right. What it should reach next and does not: "Therapist signs" (step 6) and the Signature card, which
are the product; both are the same weight as everything round them.

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| D1 | **150% zoom: the pick is below the fold.** `#rows` (shot `screen-01-shower-chair@150.png`) | At 960 x 540 the header block (title, ordering, sub, Elena line, a 6-line column header) uses 330 px; the Recommended row is cut in half at the bottom edge and the Signature card is off screen. `#rows` is 116 px high for 193 px of rows | Do not present at 150%. If zoom is needed use 125%. Or: in the `@media (max-width: 1180px)` block add `.own { display: none; } .seg button:nth-child(n+4) { display: none; } .sub { margin-bottom: 0.25rem; }` | S |
| D2 | **150%: total clipped.** `.top .total` | "Total $114.69" runs off the right edge, the last digit is cut (`span @903,15`, page scrolls 2 px sideways) | `@media (max-width: 1180px) { .top .total .tl { display: none; } .toolsbtn { display: none; } }` | S |
| D3 | **150%: "✓ Recommended" pill cut by the row border** | `.res.pickd` is `white-space: nowrap` in an 88 px column | `@media (max-width: 1180px) { .res.pickd { font-size: 0.75rem; padding: 0.125rem 0.375rem; } }` and widen the last column to `minmax(7rem, 8rem)` | S |
| D4 | **Column header, 1440.** `.hd .lh` for a limit (shot `screen-01-shower-chair@1440.png`) | Four stacked lines in one header cell: "Weight capacity / ≥ 300 lb / Dana's limit · phone only (wraps to two) / Ask Dana", beside a two-line "Overall width ≤ 21.5 in". The header row is 84 px and ragged; 11 px grey on white is the smallest text on the page and unreadable from a room | Drop `.own` from the header (`.own { display: none; }`); keep one control: "Ask Dana" → **"Dana's limit"** as the link text (it says whose it is and is the control). Header returns to three lines everywhere | S |
| D5 | **Why panel clipped mid-sentence.** `.side .why` | 615 px of content in 443 px; "returns “The store’s information doesn’t" is cut at the card edge with no fade; "Reviewers say" is never seen | One line per quoted answer: `.pair.agent .kv .qt { -webkit-line-clamp: 1; }`; and say the check once, not under every limit: `.pair + .pair .guards { display: none; }`. Saves about five lines; the panel then ends cleanly on "Reviewers say" | S |
| D6 | **Signature card headline wraps with an orphan.** `.signs` | "Dana signs: 6 limits · the quotes · 3" / "picks · $114.69" | Words: **"Dana signs 6 limits · 3 picks · $114.69"** (drop "the quotes ·"); fits one line at 15 px | S |
| D7 | Under the pill: "3.9 · 28 reviews · amazon.com" | A bare 3.9; and a second store name (amazon.com) under a parentgiving.com product reads as "bought on Amazon" | "★ 3.9 (28 on amazon.com)"; or remove it from the row, it is already in the Why panel | S |
| D8 | Step 5 "Picked $41.99" beside "Total $114.69" | Two money figures in the bar that differ; Trail says "Picked 3 items · $114.69" for the same step | Sublabel: **"3 items · $114.69"** on both pages | S |
| D9 | "42 read · 1 cheaper rejected" under the title, "34 rejected, with reasons" in step 4, "+ 40 dearer (7 pass), not needed" | Three counts of the same set, none adds up at a glance (1 + 33 = 34) | Sub line: **"42 read · 34 rejected · 8 pass"**; keep "+ 40 dearer, not needed" without the bracket | S |
| D10 | "Elena · the home: tub inside 21.5 in" on shower chair; **"Elena · ask the agent"** on grab bar (shot `screen-03-grab-bar@1440.png`) | The same slot is a fact on one item and an instruction on another; "ask the agent" has no object | Grab bar: "Elena · no measurement needed"; keep the click | S |
| D11 | Elena drawer heading **"Elena · invented"**; caption "Ask the agent" directly over placeholder "Ask the agent…" (shot `screen-32-elena-home@1440.png`) | "invented" reads as a status of Elena; the label is said twice; 420 px of empty panel under it | Heading "Elena"; delete the `Ask the agent` caption; placeholder "Ask about this item…" | S |
| D12 | Top bar meta **"invented people, real stores"** | Seven other things in the bar; this is a disclaimer in the place of a subtitle, and "invented" appears again in the drawer | Move to the foot of the left list as 12 px grey, or shorten to "demo names · real stores" | S |
| D13 | Tools drawer, rows open (shot `screen-31-tools-all-open@1440.png`) | About 300 words; internal ids and paths on stage: `sie:Qwen/Qwen3.8-27B-FP8`, `/api/senso/checks`, `evals/firedrill/*/report.txt`, campaign ids `5fa2f8da, 630ecf19`, ISO timestamps, "1 writes refused", a double full stop "just now..", and a failing score in plain sight: **"Names who can make the change 70.5 (threshold 75) … every criterion met: no"** | On stage open the drawer but **no row**. The closed list (shot `screen-30-tools@1440.png`) is clean: 8 names, 8 numbers. If a row must open: cap `.tooldetail` at the bold sentence (`.tooldetail .faint, .tooldetail code { display: none; }`) | S |
| D14 | Tools legend "● the tool's own check holds · ○ read the detail" | Every dot is green, so the legend explains a state that is not on screen | Delete the legend line | S |
| D15 | Rejected row panel: key "why it is unclear" wraps in a 60 px column (shot `screen-11-rejected-row@1440.png`) | Two-line key beside a one-line value | Key: **"why"** | S |
| D16 | Chip "13.5 no unit" and result "✕ unclear · no unit stated" | Said twice in one row | Chip: "13.5 ?"; keep the result text | S |
| D17 | "(21.5 in · measured last time)" in the list | "last time" has no referent for a stranger | "(21.5 in · Elena measured)" | S |
| D18 | Type scale | 7 sizes (11, 12, 13, 13.44, 14, 15, 20 px), 3 weights, 3 families (Inter, Georgia, mono) = 16 combinations. Outliers: 11 px/400 (`.own`, `.ask`), 15 px (`.why h2`, `.signs`), 13.44 px Georgia (`.paper`, 0.84rem) | `.why h2, .signs { font-size: 0.875rem; }` with weight 600 is enough; `.paper { font-size: 0.875rem; }`; D4 removes the 11 px | S |
| D19 | Colour | Indigo `#4f46e5` is used once (the pick): good. Green tick, red figure, amber mark each carry one meaning and each has a glyph or word beside it (✓, ✕, "250 lb, under 300"). No colour-only meaning found. The pale `#f1f2f4` selected item and the `#f7f7ff` pick row are close in tone: fine on a laptop, will merge on a washed-out projector | `.rowx.picked { border-width: 2px; }` | S |
| D20 | Opening motion (shots `screen-51-switch-f00..f02@1440.png`) | Good: rows are checked top down, cells and reasons fill, the pill lands; real data. Two flaws: the Why card is **absent** for the first 1.2 s so the right column jumps from one card to two; on the shower chair (2 rows) the whole thing is over in under 0.5 s and is not seen | `fx.arrive` the Why card's content, not the card: keep the empty card frame in place from t=0. Open the demo on **Grab bar** (7 rows), where the motion reads | S |
| D21 | Stepper: steps 6 and 7 | Only an outlined number separates "not done" from "done"; "from the phone" is the dimmest text in the bar although it is the next thing that happens | `.step.now .l { font-weight: 600; } .step.now small { color: var(--t1); }` | S |
| D22 | Title menu (shot `screen-33-title-menu@1440.png`) | Works; the caret "▾" is 12 px grey and the title does not look pressable | `.sheet .caret { color: var(--t2); }` | S |

Controls on `/`, all pressed: 3 items, 7 steps, Tools at work and its 8 rows, the Elena line, title menu, rejected
row, "+ 40 dearer", "Back to the pick", the store "page ↗" link (opens the real product page). Hover and focus
states exist on all (2 px ink outline). `Ask Dana`, the ordering control and the second list are on the copy, below.

On the copy (`web/screen`):

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| D23 | Ask Dana drawer (`x-screen-unsigned-20-ask-dana-f1@1440.png`) | Clean. Three sentences where one will do | "Elena proposes; Dana decides on the phone." | S |
| D24 | Signed card (`w-screen-41-signed@1440.png`) | "self-declared", "Sheet hash d4d609db2348", "Hash covers limits, strikes, picks +7", "replay" beside each cart | "Signed by Dana · 15:09"; code grouped as on `/seal/`; delete the "Hash covers" line; delete "replay" | S |
| D25 | Signed, item with no pick | Step 5 shows an indigo ring "5 Picked · nothing passes" beside two ticked later steps; reads as unfinished after signing | When signed, `.step.now` ring only on steps after the last done one | S |
| D26 | Limit moved from the phone (`w-screen-32-limit-moved-from-phone-f00..f04`) | Works and is the best motion in the product: the header figure changes, cells turn red, reasons rewrite, the total rolls. Ends in a state that reads | Keep. Rehearse the slider to stop where a pick still exists | - |
| D27 | Second list (`w-list2-05-first-item@1440.png`) | Works. "Ms. Alvarez's limit · phone only" wraps to three lines in the header; the key "Ms. Alvarez" wraps in the Why panel; "prefers Sheets preferred: prefers at least 100 sheets." says prefer three times | D4 fixes the header; `.kv { grid-template-columns: 4.75rem minmax(0, 1fr); }`; words: "prefers 100 sheets" | S |
| D28 | Switch confirm (`w-list2-03-confirm@1440.png`) | Good: two lines, Stay / Switch | - | - |

## `/trail/` Trail (owner `web/trail`)

First landing: the dark frame "What the model sees". Right. Second should be "Never enters a model call"; it is
14 px/600 under the frame with two lines crossing behind it.

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| R1 | Rail against content (T9) | Steps 6 and 7 are named for things the replay does not show | Rename in the replay: "Asked the store", "Remembered" | S |
| R2 | Empty lower half during Play (`trail-31-play-f02@1440.png`) | Captions "TO THE STORE'S OWN AGENT" and "MEMORY · EACH FACT HAS AN OWNER" sit over 270 px of white until 0:18 | Hide a row's caption with its row (`.later`), so the frame grows downward as it plays | S |
| R3 | Play scrolls 16 px | The card's top edge meets the bar; a visible jump at the first press | `flow.js:201`: `block: "nearest"` for every step (it is `"start"` for the first four) | S |
| R4 | "What left" matrix (`trail-20-what-left@1440.png`) | "~~stopped~~ 6": a struck-through "stopped" reads as "not stopped". 27 cells of "not recorded". Red "found 1", "found 27" with no noun. Header "125 payloads to 5 recipients" over six columns; on a small run it prints "1 recipients". Lower-case tool names. The count rises while the page is open | Do not open on stage. If kept: no strike on the word (`.lv.stopped { text-decoration: none; font-weight: 600; }`); empty cells for `.lv.unknown` (`.lv.unknown { visibility: hidden; }`); "found 27" → "27 not declared" | M |
| R5 | Guard row | The best frame in the product. "the agent's draft" marks words in red by colour alone until the chips strike them; the reply is highlighted yellow from first word to last, so the highlight means nothing, and it ends "only if …" | Draft: add `text-decoration: line-through` to the red words. Reply: highlight only "does not specify expedited shipping or guarantee arrival by December 2" | S |
| R6 | Memory shelf | "The shopper measured the tub_inside_width: 21.…" (internal id, truncated); the shelf is cut by the fold at 810 ("16 more" at y 797) | "Tub inside width 21.5 in · Elena measured"; to lift the shelf above the fold, `.fl-by { height: 72px; }` (it is 96) | S |
| R7 | Captions | UPPERCASE small captions exist only on this page | `.fl-stage .cap.up { text-transform: none; letter-spacing: 0; }` | S |
| R8 | Connectors | Where two lines share a path they draw as a doubled dark-and-grey stroke (left cards to the frame, frame to the chips) | One stroke colour per path: `stroke: var(--t3)` for bypass lines, `var(--t1)` only for the line into the frame | S |
| R9 | Record under the picture (`trail-21-band-and-steps@1440.png`) | Each step row carries "≡ 5 [ ] 4 ▶ 6": three glyphs with numbers and no words. The line "9 model calls · 3 given page text · none saw a limit · **3 saw a person's name**" sits under a picture headed "Never enters a model call" and will be read as a contradiction | Hide the glyph counts on the rows (`.sr .kt { display: none; }`; the filter chips carry the same counts with words); reword to "3 were given a first name (Dana, Elena), none a limit or a measurement" if that is what it counts, else do not scroll here on stage | S |
| R10 | Second list (`w-list2-10-trail@1440.png`) | "No question record", "no guard record", "No reply record", "0 dB to spare" | Hide the row when there is no conversation; "exactly at the limit" | S |

Motion: 7 steps in 24 s, each step adds real text from the run and every paused frame reads. 150%: the stage
scales as one piece and stays correct; text drops to about 9.5 px effective, so this page too is better at 100%.

## `/graph/` Memory (owner `web/graph`)

First landing: the right panel's 20 px question and 150 words of answer, not the graph. It should be the pick.

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| G1 | "The run" (T6) | Dots without labels; 10 px edge words ("wrote", "measured", "is why she measures and receives") | Default to "The decision" | S |
| G2 | Stage 2 "The order" (`graph-40-play-f09@1440.png`) | 26 boxes: hospital scheduling, Marcus, discharge planner, "Rosa weighs about 280 lb"; second lines truncated to "not sent to a store or a sto…"; edge labels lie on top of the lines | Cut from the demo; if kept, show only the 5 boxes with a dark border | M |
| G3 | Answer panel | Ends on a colon: "Carex.com lists two walker candidates:"; the walker answer talks about the tub | Cut the short answer at the last full stop, not mid-list; keep "the whole answer" | S |
| G4 | "Rosa's hip replacement · Nov 24 to Dec 2" | A boxed node alone in the bottom-left corner with no line to anything, dates differ from stage 2 ("Nov 12 to Dec 2") | Remove from the last stage or attach it (commit `72b7267`, made after these shots, touches the dates: re-check) | S |
| G5 | Band, right side | "Graph: the run's records" and "Answer: Cognee" look like buttons (pills) and are not | Plain 12 px grey text | S |
| G6 | "The decision" (`graph-31-decision-shower-chair@1440.png`) | Good. Outcome lines truncate: "the pick · $41.99 · parentgiving.…"; "39 more products · 20 not stated · 11 outside · 7 meet…" | Widen the last column: `WIDTHS[4]` 210 → 260 | S |
| G7 | 150% | T1 | - | M |

Motion: Play steps 11 stages at 1.7 s with tweened positions; smooth, no restart. It ends in a state that needs
explaining (G1).

## `/seal/` Signature (owner `web/seal`)

First landing: the fingerprint block and code. Right. After a change: the red code and "Not what Dana signed". Right.

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| S1 | `seal.js:174` "Try to get a cart without her." / "Replay her signed request" / "Change her limit from the laptop" | "her" has no name before it on this page | "Try to get a cart without Dana." / "Replay Dana's signed request" / "Change Dana's limit from the laptop" | S |
| S2 | Attempt rows (`x-seal-unsigned-13-attempts-after@1440.png`) | Mono grey `sign_sheet · no signature`, `set_limit L1.capacity 600 → 500 lb · no signature`, `the same bytes again · seq 1795216182497`; result "**401** unsigned · not signed by the approver's key" three times | Hide the mono column (`.try .sent { display: none; }`); result: "Refused · not Dana's key" in `var(--bad)` with ✕ | S |
| S3 | "· Default Title" after the walker; lower-case product names; "seq 1795216182497" under Verified | Store internals | Drop a variant equal to "Default Title"; `text-transform: capitalize` is wrong for brand names, so print the title as the store has it; delete the seq line | S |
| S4 | Lead sentence, 25 words | "Change one thing. Click any value: this browser recomputes the fingerprint and checks the real signature, without trusting our server." | "Change any value. This browser re-checks the signature itself." | S |
| S5 | "Who holds what" | Pushed under the fold at 1440 by the attempts card: only its three headings show | Put the attempts card last | S |
| S6 | "✕ signature over this copy" | Not a sentence | "✕ signature does not match" | S |
| S7 | Quantity "1" is an 8 x 21 px button; values are underlined with a dashed 1 px grey line only | Small target; the only hover change is the dashed underline turning ink, invisible from a seat | `.val { padding: 0 0.25rem; } .val:hover { background: var(--bg); }` | S |
| S8 | The fingerprint block looks like a QR code, and `/` has a real QR | A judge may try to scan it | Keep; say "pattern, not a QR" in the narration, or round the cells (`.pat i { border-radius: 50%; }`) | S |

Motion: a committed edit turns the row pale red, strikes the old figure, changes the pattern and code in the
same frame (`w-seal-07-edit-commit-f00..f03`); Restore returns it. Immediate and legible. 150%: the fingerprint
moves above the rows and everything fits the width.

## `/talk/` Conversations (owner `web/talk`)

First landing: a paragraph in bold yellow. It should be the band: "may receive / never".

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| C1 | Replies | Four-line passages in bold on yellow; elsewhere yellow marks one figure | `#thread mark { font-weight: 400; }` and mark one sentence per reply | S |
| C2 | Thread | Two "Sent" messages that ask the same thing; the second reply is cut by the fold | Show the last exchange only, the rest behind "+1 earlier" | M |
| C3 | "Withheld a person 2 · health detail 2 · order limit 2 ▾" then the same chips with no numbers | Inconsistent; the caret is 10 px | Always the count; `.caret { font-size: 0.75rem; }` | S |
| C4 | List: "+3 more" opens "the shopper asked · not sent" twice | Names (T7); "not sent" has no reason | "Elena asked · held by the guard" | S |
| C5 | Opens on the last store (T3); no total, no Not signed pill (T2) | - | - | S |
| C6 | Sent text "does not fit her needs" under "Withheld: a person" | A judge reading closely sees a person referred to in a message that claims to withhold one | Narration only; or reword the stored question | S |

150%: the band wraps to two rows and stays legible; fine.

## `/phone/` (owner `web/phone`)

First landing after enrol: the first item card. It should be what Dana is asked to do; the Sign button is 1100 px down.

| # | Element | What is wrong | Exact fix | Size |
|---|---|---|---|---|
| P1 | Sign button (`w-phone-05-sheet-full@phone.png`) | Below three cards, the total, three check lines and the hash | `#sign { position: sticky; bottom: calc(56px + 8px); }` so it is always on screen | S |
| P2 | Code (T4) | 64 hex characters | First 12, grouped, 20 px | S |
| P3 | "Why this one" | `350 >= 300`, `17 <= 24`, and `“Width (outside legs): 17"”` with doubled quote marks; "needed by 2026-12-02" | "350 lb ≥ 300 lb"; no added quotes when the text ends in `"`; "needed by Dec 2" | S |
| P4 | Pick line | "carex.com · Default Title · × 1 · USD" | "carex.com" (add "× 24" only when the quantity is not 1) | S |
| P5 | Checks | "identity not checked · check identity", "Live human check (sandbox) · open", "Checking the sheet against the order…" then on the signed screen "identity check started (sandbox), not finished · inq_At7PF… · created · sandbox" and "Senso check still running" | One line each with a tick or a dash; never the inquiry id | S |
| P6 | Signed card | "Dana (self-declared)", the 64-character hash, "Open the cart · replay" | "Signed · Dana · 15:09", the 12-character code, "Open the cart" | S |
| P7 | Enrol | Two sentences about keys; "Name on the seal" | "This phone holds the signing key."; "Your name" | S |
| P8 | Tabs "Sheet / Items / Adjust a limit" | "Sheet" is the builder's word | "Sign / Items / Limits" | S |
| P9 | Limits (`phone-contact-2.png`) | Good: one row per limit, the slider, "from the order: 300 lb", "Pick now: …". At the far end: "open: nothing inside the limits" | "No product meets 600 lb" | S |
| P10 | Slider focus | A 2 px ink box round the whole slider when focused by keyboard | `input[type=range]:focus-visible { outline: none; }` | S |
| P11 | Refused sign (`refusal-w-phone-19-after-sign-full@phone.png`) | "Not signed: identity not verified" is a 14 px red line under the button, off screen once the page re-renders at the top | Show it in the toast as well | S |
| P12 | Item names lower case | T7 | - | S |

## Controls, across pages

Pressed (tab links were checked by address: the same five on every page, all load); `/`: items, steps, Tools and its rows, Elena, title menu, rows, more, Back to the
pick, page link, ordering (5), Ask Dana, Choose this one, the home slider. Trail: ‹, Play, 7 rail steps,
What left, a filter chip, an event row (› not pressed). Memory: 3 items, 2 views, Play, a node and the fold node in the decision view, the whole
answer (‹ › and a node in the run view not pressed: my click on an SVG node timed out). Signature: a value (edit, Enter), Restore, the cart-coverage toggle, 3 live attempt buttons (each
answered 401 and logged a row with the time). Conversations: every store's thread, the first "+ more", Withheld. Phone: Enrol (with
and without a code), 3 tabs, Why, a limit's quote, Strike…, a slider, check identity, Sign twice.
No dead link and no console error on the live pages. Focus ring: 2 px ink on all. Disabled states exist
(ordering after signing at 60% opacity; "Replay her signed request" before any signature). Small targets:
"Ask Dana" 49 x 16 px; Signature quantity 8 x 21; "Withheld ▾" 22 px high; Memory products in the run view
13 x 15 px.
