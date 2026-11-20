# Review as a judge, 1440 x 810

Reviewed 14:36 to 14:50 against the live instance (GET only; every non-GET request was blocked in the
browser) and a private replay copy on port 8031 for the two clicks that change state. Not exercised: enrolling
the phone, the limit slider on the phone, signing, carts, the second sheet. Screenshots are in
`NOTES/shots-judge/`.

## 0. Cold read of `/` (written before DEMO.md was opened)

**After 5 seconds.** A price comparison table for medical supplies. A list on the left with prices, a table
with one row marked "picked", a total of $114.69 top right. The step bar says five things are already done.
I would call it "a shopping agent that finished before I arrived". Nothing on screen says who the three
people are or why a therapist is involved.

**After 30 seconds.** A therapist (Dana) wrote requirements in sentences; the yellow figures in her sentences
became column limits; an agent read 91 store pages and took the cheapest product that passes. The first thing
that made me look twice was the grey chip `13.5 no unit` with "unclear · no unit stated": a cheaper product
was turned down because the store's page did not say inches. Second: steps 6 and 7, "Therapist signs / Carts
none exist yet". So the agent is waiting for someone who is not the shopper. That is the product, and it is
the two dimmest items on the screen.

**Still not understood after 2 minutes of clicking.**
- Who is using this laptop. Elena appears only as a small link at the bottom left. The three parties are never
  on the Decision screen together.
- What "3 readers agree", "sits with its label" and "every stated value passes" mean. I guessed readers are
  people.
- What Dana will actually sign. The Signature card is a QR code and an enrolment code.
- Why "7 dearer ones also pass" and "+ 40 dearer, not needed" are different numbers.
- What "remembered" refers to, and what the numbers in "Tools at work" count.
- That "change" under a limit is an attempt the server refuses. I found that by accident; it is one of the
  best things here.
- Nothing moves. Every step is ticked on arrival, so I never see context become a decision on this screen.
  The Trail does that, but I had to find it.

## 1. Three moments that say "more than a shopping agent"

| # | Moment | Shown without narration today? |
|---|---|---|
| 1 | **Authority is split, and the screen enforces it.** The shopper's laptop cannot move the therapist's limit ("Refused · not signed 401"); the limit moves from the therapist's phone, the pick moves on the laptop, and carts exist only after her signature. | **No.** The refusal is a small tooltip behind a 10 px grey "change" link (shot `13-change-copy.png`). Steps 6 and 7 are greyed. This is the strongest idea and the least visible. |
| 2 | **What the model is not given.** On the Trail, one page of store text enters "What the model sees"; the chips "at least 300 lb" and "21.5 in" travel round it to "Checked in code"; in the guard row, "My mother", "280 lbs", "hip surgery" are struck before the store's own agent gets the message. | **Mostly yes**, once Play runs (shots `25-trail-motion-live-08s.png`, `-18s.png`). The key line "never enters a model call" is the smallest, palest text on the page. The guard row needs no words at all; it is the best single frame in the product. |
| 3 | **It refuses what it cannot quote.** Grab bar: 18 cheaper rows rejected, each with a reason in the store's own figures; "option says 18 in, page describes 12, 16, 24 in"; "never states weight capacity". | **Yes** (shot `03-grabbar.png`). This screen reads on its own. It is also the moment closest to "shopping agent with criteria", so it should be short and come before 1 and 2, not carry the demo. |

A fourth, underused: **the agent talks to each store's own agent** (`/talk/`, "8 with the stores' own agents",
"31 withheld"). Agent-to-agent with a visible withholding rule is rare among twenty demos. The guard row on
the Trail already covers it; `/talk/` itself is too wordy to show.

The sentence that answers the builder's doubt: a shopping agent decides for you; this one is not allowed to
decide. It reads, quotes and waits, and the person who wrote the rules signs the reasons. Say that; the
criteria table is only the evidence.

## 2. Confusing or unfinished, ranked by effect on a judge

S = under 10 minutes, M = 10 to 25, L = more.

| # | Page · element | What I expected | One-line fix | Size |
|---|---|---|---|---|
| 1 | `/` · Signature card (QR, "Scan to enrol the phone", "code 87bde8") | What will be signed, by whom | Enrol before going on stage; the card's headline should read "Dana signs: 6 limits · the quotes · 3 picks · $114.69". Shot `01-home-5s.png` | S |
| 2 | `/` · "change" under a limit, and its tooltip | A sign that this is the shopper trying and being refused | Rename the link "try to change"; make the refusal a line in the column header that stays 4 s: "Refused: only Dana's phone can change this". Shot `13-change-copy.png` | S |
| 3 | `/trail/` · "never enters a model call" | The headline of the figure | Same size and ink as "What the model sees"; delete the "no ledger rows" chip under it. Shot `25-trail-motion-live-08s.png` | S |
| 4 | `/trail/` · Play | Animation | Play jumps straight to the last frame when the OS has Reduce Motion on or the browser is automated (a scripted recorder). Open `/trail/?motion=1` on stage and in the recording; verified that this plays all seven steps in 24 s | S |
| 5 | `/` · "Tools at work" drawer | What each number counts | "SingleStore 8", "Airbyte 311" have no noun; the caption promises a route "named under it" and none is. Add the noun to each row or do not open it on stage. Shot `07-tools.png` | S |
| 6 | `/` · "3 readers agree", "two readers agree", "sits with its label", "every stated value passes" | Plain words | One line: "✓ quoted from the page · 3 models read the same figure". Also "3" and "two" are mixed | S |
| 7 | `/` · "7 dearer ones also pass" against "+ 40 dearer, not needed" | One number | "+ 40 dearer (7 pass), not needed" | S |
| 8 | `/` · step bar, all five ticked on load; step 4 says "Checked · cheapest first" | Something that happened | Step 4 sublabel: the count rejected ("20 rejected, each with a reason"). Give steps 6 and 7 full ink; they are the point | S |
| 9 | `/` · "Elena: measurements, chat" at the foot of the list | The third party, visible | Move it under the list title as "Elena · the home: tub 21.5 in · door 28 in"; the slider behind it is a live moment that is hidden today. Shot `10-elena.png` | S |
| 10 | `/` · chat placeholder "Put the struck one back…" | A neutral prompt | "Ask the agent…" | S |
| 11 | `/` · "(21.5 in · remembered)" | Remembered from where | "(21.5 in · measured last time)" | S |
| 12 | `/` · "$114.69" top right, and "❚❚ 2 receipts verified" | A label; an icon that means verified | "Total $114.69"; replace the pause-like glyph with ✓ | S |
| 13 | `/trail/` memory shelf · "The shopper measured the tub_inside_width: 21.5 in." | Words | "Tub inside width: 21.5 in · Elena measured" | S |
| 14 | `/trail/` step bar · "Picked $114.69", "Checked 61 inside" | The same words as `/` | "Picked 3 items · $114.69"; "61 pass" | S |
| 15 | Navigation differs on every page: `/` has Decision, Trail, Conversations; `/trail/` has Decision, Trail; `/graph/` has Decision, Trail, Memory; nothing links to `/graph/` | One bar | The same four links everywhere, or never navigate by the bar on stage | S |
| 16 | `/graph/` · right panel, about 150 words of Cognee prose, clipped mid-sentence at the fold | A short answer | Cap at three sentences, one per owner; the columns on the left already say it. Shot `30-graph.png` | S |
| 17 | `/graph/` · the two store nodes at the bottom with long empty "sold by" lines | Stores next to their products | Drop the store row; the store is already in each product's colour | M |
| 18 | `/talk/` · five threads with the same store, three marked "not sent" in red | Why not sent | "not sent · guard stopped it", or hide them; red reads as failure | S |
| 19 | `/talk/` · the header chips ("may receive" / "never") | Larger | This rule is the page; make it the first thing read, 16 px | S |
| 20 | `/phone/` without a code · "A key was made in this browser and cannot leave it…" | Fine, but two sentences | "This phone holds the signing key." Shot `50-phone.png` | S |
| 21 | `/` · "Why this one" panel overflows; "The store's agent said" is cut at the fold at 810 | The store agent's answer visible | Fold the three check lines into one (item 6) and it fits | S |

Top five for the time left: 1, 2, 3, 4, 8. All are text or style, none touches the engine.

## 3. Text to cut

A judge reads headings, numbers and anything coloured. Everything below is read by nobody in three minutes.

- `/` header: "3 items · invented people, real stores" → keep "invented people, real stores"; drop "3 items".
- `/` list title: "Dana's list · occupational therapist · invented" → "Dana · therapist · her order".
- `/` table subtitle: "Cheapest first. 42 read · 1 cheaper one rejected · 7 dearer ones also pass" → "42 read · 1 cheaper rejected".
- `/` Why panel: "the list says", "the store states · option: Gray", "from the home" → "Dana", "the store", "Elena" (the coloured dots from the Trail would do it with no words). Cut "sits with its label" and "every stated value passes".
- `/` Why panel: "delivery (this product) · stated, not guaranteed" → "delivery · the store states".
- `/` Tools drawer: "One real number per tool, each from the route named under it." → cut.
- `/trail/`: "What each party said", "Checked in code" are good; cut "claude-sonnet-5-5 · prompt builder", "what each figure means" and its paragraph (keep the box, one line), "no ledger rows", "left: product name · need-by date" → "sent: product name, date".
- `/trail/` guard: "Guard · stopped here" is right. Keep.
- `/graph/`: "Graph: the run's records", "Answer: Cognee", "15 of 441 nodes", "Cognee · 6 datasets · 29 s · 14:03", "Cognee built its graph in 2 min 7 s" → keep one: "answered by Cognee".
- `/talk/`: the second, near-duplicate question and reply in each thread; show one exchange per store.
- Everywhere: timestamps (13:54, 14:02, 14:13). They date the data to earlier today and add nothing.

## 4. The run of show

What DEMO.md gets right: opening on the order, the grab-bar rejections, the Trail, the phone. What I would
change:

- **The phone is at 1:30.** The split of authority is the idea, and it arrives at half time after 75 seconds
  of table and diagram. Twenty demos in, attention is highest in the first minute. Show the refusal on the
  laptop by 0:25 so the judge knows early that this agent does not decide.
- **Cut the second sheet at 2:30.** It costs 15 seconds, it resets the run (DEMO.md says so itself), and
  "same engine, other list" is a claim judges take on trust. Put it in the video only.
- **Cut the memory shelf beat** unless it is rehearsed twice; it is the least legible row on the Trail.
- **End on the signed screen**, carts linked, not on a different list.
- **Sponsor sentences:** at most two, while pointing. The Tools drawer as it stands invites "what is 311?".

| Time | Screen | The one thing the eye should be on | The words |
|---|---|---|---|
| 0:00 | `/`, unsigned, Shower chair | Dana's sentences, yellow figures | "A patient comes home after surgery. His therapist wrote what the house needs. His daughter shops. Neither can pick the product alone. This agent reads the stores for them, and it is not allowed to decide." |
| 0:15 | click **Grab bar** | the red figures, then the two "unclear" rows | "Cheapest first. Eighteen cheaper bars rejected, each on the store's own figure. These two are sold as 18 and 36 inch on a page that describes neither. Unclear is not bought." |
| 0:35 | click **change** under the limit | "Refused" | "The daughter's laptop tries to lower the therapist's limit. Refused. The rule belongs to the person who wrote it." |
| 0:45 | `/trail/?motion=1`, Play | the store page entering the frame; the two chips going round it | "This is everything the model is given: one page of the store's text. Her limit and the tub's width never go in. Code compares them." |
| 1:10 | Trail keeps playing: guard row | the struck chips | "Our agent asks the store's own agent about returns. The guard strikes the mother, her weight and the surgery before it is sent. This is the store's reply." |
| 1:25 | `/`, Shower chair; phone in hand, drag the limit past 350 | the highlight leaving one row for another | "The therapist raises her limit from her phone. The pick moves, to another store, and that store states opened bath seats cannot be returned." |
| 1:55 | phone: **Sign**, two taps | steps 6 and 7 turning dark; the cart links | "Only now do carts exist, at the real stores. She signed the limits, the quotes and the picks, not a total. Nothing is checked out." |
| 2:20 | `/`, signed | the two cart links | one sponsor sentence if its figure is on screen |
| 2:30 | stay | the whole signed screen | "It read every page, turned down what it could not quote, kept what the store did not need to know, and waited for the person who wrote the rules. The people are invented; the stores and the carts are real. Sign-Off." |
| 2:45 | spare | | 15 seconds held for the phone |

This leaves fifteen seconds of slack, which the phone beat will use.

## 5. The biggest risk, and the fallback

**The phone.** The central moment runs phone → Cloudflare quick tunnel → laptop on a venue network with twenty
teams on it. If the tunnel address changes, the QR on screen is stale and re-enrolling on stage takes longer
than the beat. A slider that will not land past 350 first time costs ten seconds with the room watching.

Fallback, decided before 16:50 and not on stage: a second browser window at 390 wide with `/phone/` already
enrolled and resting on the limit screen, placed beside the main window. If the real phone has not responded
within three seconds, say "the same page, on the laptop" and use it. It makes the same signed requests.
DEMO.md lists this; it needs to be the rehearsed default, with the real phone as the bonus.

Two smaller ones: Play on the Trail silently jumps to the end under Reduce Motion or an automated recorder,
so use `?motion=1` (item 4); and the title menu resets the run, which is a reason to drop the second sheet.

## 6. Are the open items the right bets?

| Item | Verdict |
|---|---|
| Ordering control (Cheapest / Best reviewed / Best value / Most reviewed) and preferences | **Wrong bet for the stage.** It is the most shopping-site control there is and feeds the builder's own doubt. If it lands, leave it on "Cheapest" and mention it only if asked "why the cheapest?". Do not demo it. |
| `/graph/` growing as an explored graph | **Not for the three minutes.** The Trail replay already shows context becoming a decision, and it is rehearsed. A second animated figure competes with it. The current `/graph/` columns (who, what they said, the rule, the product's words, the outcome) are a good still for the video's last card. |
| `/seal/` page | **Right idea, wrong place.** "She signed the reasons, not a total" is the claim that separates this from signed-payment work, and nothing on screen shows it today. A new page is one more navigation in a three-minute run. Put its one line on the Signature card and the phone's sign screen (item 1); keep `/seal/` for Q&A. |

With the time left, the five small fixes in section 2 and two full rehearsals of the phone beat are worth
more than any of the three.
