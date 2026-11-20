# Demo run-of-show

Rewritten 15:25 on the approver as the spine, from four independent reviews (`NOTES/PITCH-1520.md`,
`NOTES/REVIEW-everything-1500.md`, `NOTES/REVIEW-approver-1500.md`, `NOTES/REVIEW-design-1508.md`) and the
recording plan (`NOTES/RECORDING-PLAN.md`). A beat marked [verify] has not yet been seen working on main by
the integrator; the 15:42 check settles each one. Numbers are read off the screen, never from memory.

## The problem, in one sentence
The person who wrote the rules is not the one shopping, and at the moment of buying the rules get bent
without her.

## Opening and close, word for word
- **Opening (15 s):** "Whoever writes the rules is rarely the one shopping. Rosa comes home from a hip
  replacement on December 2. Her therapist wrote what the house needs. Her daughter's agent shops three real
  stores. It cannot bend those rules, and no cart exists until the therapist signs."
- **Close, live (20 s):** "Today the approver is a therapist. It could be a manager, a grant holder, a
  payer: anyone whose rules someone else spends against. What is missing is the other side: a store or a
  payer that checks this signature before it takes the order. Once agents shop, we are all the person who
  was not there." Last line: "A shopping agent decides for you. This one waits for the person who answers
  for it. Sign-Off."
- **Close, video (last card and voice):** "Built today: her order, the stores' own words, her signature,
  real carts, nothing checked out. Not built: anyone on the other side checking that signature. The people
  are invented. The stores, pages and carts are real." Last line: "She signed the reasons, not the total.
  Sign-Off."

## The three minutes, live
Before walking up: tab 1 is `/` with Shower chair selected; tab 2 is `/seal/`. The phone is in the hand,
enrolled, identity check done, resting on the sheet. **The peak is Dana's two taps and the cart links
appearing, at about 1:35.** The failed check at about 2:00 is the proof that follows it.

| Time | Screen and click | Eye on | Words |
|---|---|---|---|
| 0:00 | `/`, unsigned, Shower chair | Dana's sentences on the left; "Therapist signs", "Carts · none exist yet" | the opening |
| 0:15 | click **Grab bar** | the red figures, then one "unclear" row | "Cheapest first. A store's figure counts only if code finds those exact words on the store's page. This bar states 75 pounds. Her order says 300. This one never states the figure. Unclear is not bought." |
| 0:33 | click **▶ Replay the run**; after about 10 s, **Back to the list** [verify: photos, not circles] | products being set aside by a rule | "How it got here: her order, three stores, every page read, each rule setting products aside." **Cut this beat first if the clock is behind, or if the replay is not clean.** |
| 0:47 | click **Shower chair**, then **Ask Dana** under the weight limit; enter 375; send [verify] | the dialog's line: "Dana decides on the phone; nothing changes until then" | "Here is where a shopping agent just does it. Elena wants more margin than 300 pounds. She cannot change the rule. The agent cannot. She can ask." |
| 1:02 | the phone: Dana's phone shows the ask; she accepts [verify] | on the laptop: the limit changing, the pick moving to another store | "Dana decides on her phone. The rule is hers. The pick moves to another store." Fallback, seen working: phone → Adjust a limit → drag to 375. |
| 1:22 | the phone: **Sign**, tap, tap again; hold still for the carts (about 4 s) | the signing and carts steps; the cart links | **PEAK.** "Until this tap, no cart existed anywhere. Now there are carts at the real stores. Nothing is checked out." |
| 1:45 | tab 2, `/seal/`, reload | "A signature over the cart covers 7 of 23 rows · here 23 of 23" (read the counts off the screen) | "A signature on a cart covers these rows. Hers covers all of them: her rules, Elena's measurements, the stores' words, the picks, the prices, the ordering." |
| 1:58 | click the **300 lb** (now 375), type another value [verify, signed] | the fingerprint changing; the signature line turning red | "Change one value. This browser recomputes the fingerprint and checks her signature again. It no longer covers this sheet." |
| 2:10 | **Replay her signed request**, then **Change her limit from the laptop** [verify, signed] | the two refusals | "These are real requests to the real server. Her own request sent a second time: refused. Her limit changed from the laptop: refused. The agent can shop all day. It cannot approve." |
| 2:25 | stay on `/seal/` | the whole signed sheet | the live close and the last line |
| 2:50 | | | ten seconds of slack; the phone will use them |

Rules for the stage:
- Leave the ordering control on Cheapest. Do not open Trail, Memory, Conversations or the Tools drawer.
  Do not use the title menu: switching sheets starts a new run.
- After signing, do not press "Ask for carts with no signature" or "Sign with a key made in this browser":
  they then answer "already signed", which shows less. Before signing they are the stronger refusals.
- Say a number only while it is on screen. The fingerprint changes with every change to the sheet: read it
  off the screen, and look at the phone and the laptop side by side before saying they match.
- Present at 100% zoom (two pages still break at 150%) [verify at 15:42].

## The 2:30 video, as a delta (shot list and assembly: `NOTES/RECORDING-PLAN.md`, `demo/recording/`)
- 0:00 the caption "The person who wrote the rules is not the one shopping." over the unsigned screen; voice:
  "Rosa comes home from a hip replacement on December 2. Her therapist wrote what the house needs. Her
  daughter's agent shops."
- Grab bar: 12 s, zoomed on the red figure and one unclear row.
- Replay the run: record it whole, show about 8 s at double speed.
- Ask Dana, the phone and the two taps in one continuous take, phone beside the laptop. Caption at the taps:
  "Until this tap, no cart existed."
- `/seal/`: the coverage counts, one value changed, one refused request. Caption: "Change one value and her
  signature no longer covers the sheet."
- Optional 8 s of the Trail (`/trail/?live=0&motion=1`), captioned "The model that reads store pages is
  given the store's text. Code does the comparing."
- Last card and voice: the video close. A caption on every spoken line; judges may watch muted.

## Getting the phone from nothing to "ready to sign" (a reset undoes all of it; about three minutes)
1. `sh scripts/run_main.sh`; `POST /api/admin/reset` only if a fresh run is wanted.
2. Scan the QR on the Signature card with the phone's camera (phone in hand; iPhone Mirroring has no camera).
   The phone says it holds the key.
3. On the phone: "check identity". It starts a Persona sandbox inquiry. On the laptop:
   `curl -X POST localhost:8800/api/admin/persona/simulate -H 'content-type: application/json' -d '{"action":"approve"}'`.
   On the phone: refresh until it says the identity check is done. Sandbox: nobody is really checked, and
   the page says so.
4. Leave the phone on the sheet. Only now start iPhone Mirroring if recording.

## 16:50 checklist
- [ ] `http://localhost:8800` shows "Home after surgery", unsigned, Shower chair selected, ordering on Cheapest
- [ ] the phone is enrolled, identity check done, on the sheet; the fingerprint's short code matches the laptop's
- [ ] tab 2 is `/seal/`; no other tab of the app is open; zoom 100%; hotspot on
- [ ] `sh scripts/tunnel.sh` printed the same address the phone is using
- [ ] the backup clip is open in another window; a second browser window at 390 px on `/phone/` is ready as
      the phone's fallback

## What can go wrong, and what to do
| Problem | Do this |
|---|---|
| The phone cannot reach the app | the 390 px browser window on `/phone/` (rehearsed) |
| "identity not checked" under Sign | step 3 above; it takes twenty seconds |
| The ask does not appear on the phone | phone → Adjust a limit → drag to 375 (the same signed change) |
| A store does not answer on signing | the cart shows "pending": say so; the signature and `/seal/` still work |
| The tunnel address changed | `sh scripts/tunnel.sh`, `sh scripts/run_main.sh`, scan again, step 3 again |
| The replay looks wrong | skip it; go straight from the grab bar to Ask Dana |
| The app will not start | the backup clip; say it is a recording |

## One true sentence per sponsor (questions and the form only; none of these is in the three minutes)
| Tool | True sentence |
|---|---|
| Senso | "Before she signs, Senso checks the sheet's sentences against her order document; a conflict on an item blocks the signature." |
| Superlinked SIE | "A second, smaller model reads the same pages, and a disagreement makes the product unclear. The same service writes the question to a store's agent and finds names in it for the guard, and embeds the memories." |
| Statsig | "We put 'both readers must agree' behind a gate and measured it: it caught five misreads and blocked twenty-seven right figures, so we kept 'a disagreement blocks'." |
| Amplitude | say only the delivered count the drawer shows [verify] |
| SingleStore | "The limit test runs as one SQL statement; its rows equal the screen's. Memory and its vectors live there." |
| Persona | "An identity inquiry gates the signature. It is the sandbox: nobody is really checked." |
| Firedrill | "A simulated shopper tried to get a struck product back. The refusal held; it scored below the bar on saying who can change it, so we changed the wording. The second run still missed one criterion." |
| Airbyte | "A local Airbyte sync delivered the stores' records for the first list" [verify the row count the drawer shows] |
| Cognee | "The run's knowledge is in Cognee, a dataset per owner; a write by the wrong identity was refused." |

## Hard questions
| Question | Answer (short, true) |
|---|---|
| Isn't this just filters plus an approve button? | "The filters are the evidence, not the product. The rules belong to someone who is not shopping, and neither the shopper nor the agent can move them. A figure the page does not state is 'unclear' and not bought; a filter lets it through. And she signs every row, so anything changed afterwards fails the check." |
| Would a therapist really approve a cart? | "Not a cart, and not today. Today she writes a list and the family guesses. Here it is half a minute: the one question only she can answer, whether her own rule can change, and a sheet showing her order was followed in the stores' own words. I have not put this in front of a working therapist. The people with the habit already are those who sign for someone else's spending: a manager, a grant holder, a payer." |
| Why not just tell the daughter what to buy? | "She cannot name the product. She knows the patient and has not seen the house; the daughter measured the house and has never bought any of this; the store knows the product. The order holds limits, not products." |
| What stops the agent or the daughter changing things after she signs? | "Nothing stops them changing a copy. Her signature just stops covering it, and her old request sent again is refused. What is not stopped today: no store checks the signature." |
| What does the signature not protect against? | "Her unlocked phone, or someone at this laptop resetting and enrolling a new approver; the identity check is a sandbox. An approver who signs without reading. And a store whose page is wrong: the quote is the store's claim, checked for being there, not for being true." |
| Why not let the model decide? | "Then she would be approving a model's opinion. Here the model only reads; a figure counts when code finds those exact words on the page, and code compares. The cost is strictness: good products that do not state the figure are left out." |
| Did a person check the figures? | "No person read every page. Each figure is a quote code found on the page, and where two readings disagree the product is unclear. That is why she is shown the quote and not our reading." |
| Why the cheapest? | "It is the default. The shopper can choose best reviewed, best value or most reviewed, or any product that passes; the phone shows her choice before the therapist signs. A rating on the seller's own page is labelled as that." |
| What does it remember, and what does it share? | "Only what a record states, each with an owner: the house's measurements, what she struck, what each store said and when. When it asks a store's agent a question, a guard in code removes limits, measurements, names and health details first. It is over-cautious: it stopped some messages it need not have." |
| Who pays for this? | "I do not know yet. My guess is whoever pays for the wrong purchase today. That is a guess, not a finding." |
| Is anything bought? | "No. Real carts at real stores, nothing checked out, invented people." |

## Words to avoid on stage
"accountable for the purchase" (say "the person who wrote the rules") · "proves", "verified", "guaranteed"
(say "states", "the check fails") · "tamper-proof", "secure" · "without trusting our server" · "her identity
is verified" · "her limits never go into a model" · "bought", "ordered" (say "carts; nothing is checked
out") · "insurance requires" · "a real therapist" · any number not on screen at that moment.

## Rehearsal log
| Time | Duration | What broke | Fixed |
|---|---|---|---|
| 11:46 | n/a | First real phone run by the builder over the tunnel: 71 signed requests, signed, two real carts. Nothing broke. | |
| 14:05 | 3:00 on a copy, replay | The director's run: unclear rows gave no reason; the 75 lb bar was hidden in the fold; "Checked against the order" shown with Senso not connected; switching sheets wiped the signed run without warning. | fixed (C12, G19, G20) |
| 14:50 | on a copy, replay | The recording director: enrol, drag the shower chair limit 300 to 375, the pick moves ("now at carex.com"), two taps, "Signed by Dana", carts about 4 s later. The identity gate blocked signing until approved. | the identity step is in the checklist |
