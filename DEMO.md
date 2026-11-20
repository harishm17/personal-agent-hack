# Demo run-of-show

Rewritten 14:15 from a director's run of the real product on a copy (every beat below was seen working
there, except those marked [if built]). Numbers are read from the screen on the day, never from memory.

## One sentence
Sign-Off shops real stores to someone else's written order: it buys nothing it cannot quote, and nothing
at all until that person signs.

## Opening and closing, word for word
- **Opening (15 s):** "A patient comes home after surgery. Her therapist wrote what the house needs; her
  daughter shops. The therapist has never seen the house, and the daughter has never bought any of this.
  Sign-Off shops three real stores to that written order, and buys nothing until the therapist signs."
- **Closing (15 s):** "It read every page, rejected what it could not quote, and waited for the person who
  wrote the rules. The people are invented; the stores, pages and carts are real. Sign-Off."

## The three minutes (lead: sheet 4, "Home after surgery"; phone already enrolled at 16:50)
| Time | Screen and click | Eye on | Said |
|---|---|---|---|
| 0:00 | Decision screen, unsigned | the order's sentences on the left | the opening |
| 0:15 | click **Grab bar** | the fold line and the red figures ("75 lb", "250 lb") | "Cheapest first. Eighteen cheaper grab bars were rejected, each for a reason. One states 75 pounds. Her order says 300." |
| 0:35 | same | the "unclear" rows | "These are sold as 18 and 36 inch on a page that describes neither. Unclear means not bought." |
| 0:50 | **Trail**, press Play [if built: the replay]; otherwise the right-hand "Why this one" panel | the page entering the model's frame; the limit going round it | "This is everything the model gets: one page of the store's own text. The therapist's limit and the family's measurements never go in. Code compares them." |
| 1:15 | [if built] step once: the guard row | the struck chips at the gate | "When our agent asks the store's agent about returns, the guard stops her limit, the tub's width and her name." |
| 1:30 | Decision, **Shower chair**; on the phone drag the limit past 350 | the highlight moving to another row | "The therapist raises her limit from her phone. The pick moves to another store, and that store says opened bath seats cannot be returned." |
| 1:55 | phone: **Sign**, tap twice | "Carts created" and the two links | "Only now do carts exist, at the real stores. She signed the rules, the quotes and the picks, not just a total. Nothing is checked out." |
| 2:15 | [if built] Trail: the memory shelf fills; **Reset**: the measurement rises back, "recalled" | the shelf | "It remembers only what a record proves, and each memory has an owner. Next time the house is already measured." |
| 2:30 | title menu → **Room 12 class supplies** → Headphones | "95 dB, over 85"; rows that never state a level | "Same engine, a teacher's list. This children's headphone states 95 decibels; this brand states none." |
| 2:45 | stay | | the closing |
Without the [if built] beats: 0:50 is the "Why this one" panel ("the model only reads; code finds the
store's own words and compares"), 1:15 and 2:15 are dropped, and 2:00 is Trail → the signing step ("every
step is a record: who enrolled, which limit changed, what was signed"). Do not touch the title menu before
2:30: switching sheets starts a new run.

## One true sentence per sponsor (only while pointing at it on screen; check each at 15:00)
| Tool | Point at | Say |
|---|---|---|
| Senso | the phone's checks line; the version tag beside the order's sentence | "Before she can sign, Senso checks each sentence of the sheet against her order, by version." |
| Superlinked SIE | a row marked unclear by a disagreement; the reader chip | "A second, smaller model reads the same pages. Where the two disagree, the product is unclear." |
| Statsig + Amplitude | the Tools drawer [if built] | "We put 'require both readers' behind a gate, measured it, and kept only the part that helped: it caught five misreads and blocked twenty-seven right ones." |
| SingleStore | the Tools drawer or the SQL panel [if built] | "The same test runs as one SQL statement; its rows equal the screen's." |
| Persona | the seal | "The signature waits for an identity inquiry. Sandbox, and the seal says so." |
| Firedrill | the Tools drawer [if built] | "A simulated shopper tried three ways to get a struck product back. It held; its refusal was unhelpful, so we changed it and ran the drill again." |
| Airbyte | the Tools drawer [if built] | "A local Airbyte sync delivered the stores' records; the query gives the same answer on its rows." |
| Cognee | the graph page's backend line | only if the page says Cognee answered |
A tool with nothing on screen at 15:00 gets no sentence.

## What can go wrong, and what to do
| Problem | Do this |
|---|---|
| The phone cannot reach the app | open `/phone/` in a second laptop window (seen working) |
| A store does not answer on signing | the cart shows "pending"; say so; or restart with `SIGNOFF_MODE=replay` (the bar says "replay of cached store data") |
| The tunnel address changed | `sh scripts/tunnel.sh`, `sh scripts/run_main.sh`, rescan the QR |
| Too small on the projector | browser zoom 150% (checked: nothing clips) |
| A judge wants to change a limit himself | hand him the phone; any value still signs |
| The app will not start | the backup clip; say it is a recording |

## 16:50 checklist
- [ ] `sh scripts/run_main.sh`; http://localhost:8800 shows sheet 4, unsigned, total as rehearsed
- [ ] `POST /api/admin/reset`; phone scanned and enrolled, left on "Adjust a limit" for the shower chair
- [ ] `/trail/` loads and Play works; zoom set; hotspot on; backup clip open in another window
- [ ] the title menu untouched

## The video (watched without the builder in the room)
Captions for every spoken line; a zoomed crop on each row as it is named; the phone as an inset. Shots:
the order's text; the red rows; the unclear rows; the replay (the page entering the frame, the limit going
round); the guard row; the slider and the pick moving; two taps; the carts; the memory shelf; the
headphones; a last card, "what is invented, what is real".

## Rehearsal (three, timed)
1. The phone beat alone until the slider lands past 350 first time (target 25 s).
2. The full run in replay mode with the network off: 0:50 Trail, 1:30 phone in hand, 2:30 the menu.
3. The full run live over the tunnel, with a real signature.

## Hard questions
| Question | Answer (short, true) |
|---|---|
| Is the reading right? | Each figure is a quote that code finds on the page; a second model reads the same pages and a disagreement makes the product unclear. No person read every page; I read the figures behind this cart myself. |
| Why not require both models to agree? | We measured it: it catches five misreads and blocks about twenty-seven right figures, so a disagreement blocks and one model's silence does not. |
| Why not just tell her which product to buy? | The therapist knows the patient but has not measured the house; the daughter knows the house but not the equipment; the store knows the product. Nobody can name it alone. |
| Why the cheapest? | It is the default. The shopper can choose any product that passes; the rules are the therapist's, the taste is the shopper's. |
| Is anything bought? | No. Real carts at real stores, nothing checked out, invented people. |
| Is this new? | Signed approvals and quote checking are not. Louck et al. showed that AP2 signs the transaction but not the decision; this puts the reasons, the limits, quotes and picks, under the approver's signature, on real stores. |
| What does it remember? | Only what a record proves, each with an owner: the house's measurements, what she struck and why, what each store said and when. Nothing a model wrote becomes a memory. |
| Is the store's claim true? | It is the store's claim. The sheet says "states". |

## Rehearsal log
| Time | Duration | What broke | Fixed |
|---|---|---|---|
| 11:46 | n/a | First real phone run by the builder over the tunnel: 71 signed requests, signed, two real carts. Nothing broke. | |
| 14:05 | 3:00 on a copy, replay | The director's run: unclear rows gave no reason; the 75 lb bar was hidden in the fold; "Checked against the order" shown with Senso not connected; switching sheets wiped the signed run without warning. | in progress (C12, SIGN) |
