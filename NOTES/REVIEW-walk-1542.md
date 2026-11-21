# Walk as a stranger, 1440 x 810 (phone 390 x 844)

Live instance http://localhost:8800 (sheet4, GET only, writes blocked in the browser) plus a copy on :8046 for enrol, ask, accept, sign.
Shots: `NOTES/shots-walk-1542/` (`live-*` = live, `phone-*` and `copy-*` = the copy).
Measured in Chrome with a DOM audit (scrollWidth > clientWidth, line clamp overflow, font under 12 px, below the fold).

## Top ten, ranked by what a viewer of the video notices

| # | Folder | Size | What the viewer sees | Smallest fix |
|---|--------|------|----------------------|--------------|
| 1 | web/screen | S | Product names in the table are cut at 160 px while the two limit columns hold "300 lb" in 132 px each. The recommended row reads "Deluxe Aluminum Bat…". Pairs become identical: "Carex Adjustable Bath…" $45.36 and "Carex Adjustable Bath…" $47.11 (full: "Carex Adjustable Bath & Shower Seat" / "… with Back"); "Carex Textured Wall G…" twice. | `ladder.css` last line (305): change `repeat(var(--n), minmax(4.75rem, 8.25rem))` to `minmax(4.75rem, 6rem)` (name column 160 → 232 px), and add `.nm b { white-space: normal; display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 2; line-height: 1.125rem; }` (the same rule already exists at line 170 for narrow screens; rows are 62 px, two lines fit). |
| 2 | web/screen | S | Nothing says whose screen this is or who the people are. "Dana's limits", "Elena · the home", "Therapist signs" appear with no introduction; Rosa appears only inside the replay. | Top bar `.meta` (`ladder.js` near 296-305), replace "invented people, real stores" with one line built from the sheet: `${shopper.name}, ${shopper.role_label}, shops · ${issuer.name}, ${issuer.role_label}, signs` → "Elena, daughter, at the house, shops · Dana, occupational therapist, signs". Keep "invented people" as the `title`. |
| 3 | web/graph | M | Replay, the row of five candidates: "Carex Adjustable…" twice, "Carex Universal…", "Medline Knockdow…", "Deluxe Aluminum…" (the pick). The difference between the two Carex seats is in the cut part. | `explore.js:255` `short(n.label, Math.max(8, Math.min(20, …)))`: draw two lines instead of one (first line = words that fit, second line = the rest, `y - p.r - px(38)` and `y - p.r - px(24)`), or at least drop the `Math.min(20, …)` cap and cut from the middle so the ending survives. |
| 4 | web/graph | S | Replay, under the candidates: "4.8 · None" (a null review count printed), "5 · 2", "3.9 · 28" with no unit, and "amazon.com" under the pick that the list says is from parentgiving.com. | Label as "4.8 ★ · 28 reviews", print nothing after the dot when the count is null, and say "reviews on amazon.com". |
| 5 | web/phone | S | The phone opens on three item cards; "Sign" is at y = 1122 on an 844 screen, under Total, Checks and a code. Header reads "Home after surgery · Dana · key 0007e1". A viewer does not learn the phone is where Dana signs. Sign also needs two taps ("Tap again to sign"), so the first tap looks like it failed. | `web/phone/index.html`: h1 `Dana signs · Home after surgery`; `#sign { position: sticky; bottom: 64px; }`; first tab label "Sheet" → "Sign". |
| 6 | web/screen | S | Right card, "The store's agent states": quotes cut to one line: "“Standard delivery generally…", "“The store's information…", "“Returns are generally limite…". The cut removes the whole fact. | `ladder.css:269` `.pair.agent .qt { -webkit-line-clamp: 1; }` → `2`. To keep the column inside 810 px, drop the "✓ 2 receipts verified" line from the Signature card (`ladder.js:696`), which a stranger cannot read anyway. |
| 7 | web/screen | S | What to do next is not stated. Step 6 says "Therapist signs / from the phone"; the Signature card at the bottom right says "Scan to enrol the phone / code 87bde8". "Enrol" is our word. | `ladder.js:727` "Scan to enrol the phone" → "Next: Dana scans this to sign". `ladder.js:397` small text "from the phone" → "next · on her phone". |
| 8 | web/screen | S | "Ask Dana" is only reachable from an 11 px underlined "Dana's limit" in the column header (`span.ask`). A stranger never finds it. | `ladder.js:565` visible text `${name}'s limit` → `ask ${name} to change` when `canAsk`; `ladder.css:251` `.ask { font-size: 0.75rem; }`. |
| 9 | web/screen | M | After Dana accepts 375 lb, the left list still reads "It must hold at least **300 lb**" for the shower chair while the table header reads "≥ 375 lb · Dana changed it to 375" and the phone reads "375 lb · changed from the order". | Left card (`ladder.js` near 430): when a limit is changed, strike the quoted number and append the new one ("300 lb → 375 lb"). |
| 10 | web/screen | S | Result cell cut mid reason: "✕ unclear · option says 18 in, page describes 12, 16,…" (full: "… 12, 16, 24 in"). In the why card of a rejected row the line "White / Each · parentgiving.com · $38.99 · page ↗" loses its "page ↗" link. | `ladder.css:69` `.res { -webkit-line-clamp: 3 }` or shorter words "option 18 in, page lists 12 / 16 / 24"; `ladder.css:244` `.meta2 { white-space: normal; }`. |

Checked and fine: `/seal/` three columns wrap instead of cutting; the four attempts all answer "✕ Refused" in place; changing a value turns the fingerprint red and "Restore" brings it back; the phone has no ellipsis cuts.

## A. Truncation and legibility

### `/` (web/screen)

| Shown | Full | Element, file | Fix |
|-------|------|---------------|-----|
| "Deluxe Aluminum Bat…" (the recommended row) | Deluxe Aluminum Bath Bench by Drive | `.rowx .nm b`, `ladder.css:57` | row 1 of the top ten |
| "Adjustable Height Bat…" | Adjustable Height Bathing Stool by Drive | same | same |
| "Medline Knockdown S…" | Medline Knockdown Shower Chair with Arms and Back | same | same |
| "Carex Portable Showe…" | Carex Portable Shower Bench | same | same |
| "Carex Adjustable Bath…" $45.36 and "Carex Adjustable Bath…" $47.11 (cannot be told apart) | Carex Adjustable Bath & Shower Seat / … with Back | same | same |
| "Carex Classics Bath & …" | Carex Classics Bath & Shower Seat | same | same |
| "Carex Universal Bath …" (recommended after the change to 375 lb) | Carex Universal Bath Seat without Back | same | same |
| Walker: "Two-Button Folding W…", "Carex Classics Dual-…" (recommended) | Two-Button Folding Walker with 5 Inch Wheels; Carex Classics Dual-Button Walker | same | same |
| Grab bar: "Carex Textured Wall G…" twice (12" and 16", told apart only by the grey line), "Drive Medical Rotatin…" | Carex Textured Wall Grab Bar; Drive Medical Rotating Suction-Cup Grab Bar | same | same |
| "Deluxe Bariatric Showe…" twice, sub line also cut: "Without Back / Each · pare…" | Deluxe Bariatric Shower Chair by Drive Medical; "Without Back / Each · parentgiving.com" / "With Back / Each · …" | `.nm b`, `.nm i` `ladder.css:58` | wider column fixes both |
| "White / Each · parentgivin…" | White / Each · parentgiving.com | `.rowx .nm i`, `ladder.css:58` | fits at 232 px |
| "✕ unclear · option says 18 in, page describes 12, 16,…" (and the 36 in row) | … 12, 16, 24 in | `.res`, `ladder.css:69`, clamp 2 | clamp 3, or "option 18 in, page lists 12 / 16 / 24" |
| "“Standard delivery generally…" | “Standard delivery generally takes 1–5 business days” | `.pair.agent .qt`, `ladder.css:269`, clamp 1 | clamp 2 |
| "“The store's information…" | “The store's information doesn't specify whether this bath bench can be returned once open…” | same | clamp 2; better, show "returns: not stated" |
| "“Returns are generally limite…" (grab bar), "“An opened walker generally…", "“Standard shipping is 3–5…", "“Opened bath seats cannot…" | the full sentences, 2 lines each | same | clamp 2 |
| "Supporting up to 440 pounds, the textured grab…" | … the textured grab bar | `.pair .qt`, `ladder.css:98`, clamp 2 | clamp 3 |
| "White / Each · parentgiving.com · $38.99 · pa…" (why card of a rejected row; the "page ↗" link is pushed out) | … · page ↗ | `.meta2`, `ladder.css:244` | `white-space: normal` |
| Header after the change: "≥ 375 lb · Dana / changed it to 375" wraps to two lines and pushes the header out of line | one line | `.hd .lh` + `.askst`, `ladder.js:564` | shorter words: "≥ 375 lb · was 300" |
| 11 px text: "Dana's limit" (`.own`, `.ask`, `.askst`), "changed from the list" (`.tag`), `.was`, `.forge`, `.prefers .pl`, step numbers (`.step .n`) | | `ladder.css:17, 48, 79, 100, 202, 250, 251, 253` | `font-size: 0.6875rem` → `0.75rem` |
| Our words on screen: "3 models agree", "2 receipts verified", "Scan to enrol the phone", "identity checked (sandbox)", "Code 2639 2093 2adf" (no word on what the code is), "13.5 ?" chip, "+ 40 dearer, not needed", "replay of cached store data" | | `ladder.js:296, 696, 727` | "3 readers agree"; drop the receipts line; "Next: Dana scans this to sign"; "Fingerprint" instead of "Code" (the seal page calls it that) |

### Replay overlay (web/graph, inside the iframe)

| Shown | Full | Element, file | Fix |
|-------|------|---------------|-----|
| "Carex Adjustable…" $47.11 and "Carex Adjustable…" $45.36, "Carex Universal…", "Medline Knockdow…", "Deluxe Aluminum…" | as in the table above | `text.pn.big.mid`, cut in JS by `short()` at `explore.js:255` | two lines, see row 3 |
| "at most tub inside 21…" under "fits inside the tub" | at most tub inside 21.5 in (the words are also wrong: "at most 21.5 in") | `text.s`, cut in JS (`explore.js`, `short()`); `graph.css:34` for the HTML nodes | shorter words: "at most 21.5 in" |
| "said to us / parentgiving.com · 1…" twice, identical | two different store answers | `text.s` | put what was said: "delivery 1–5 days", "returns: not stated" |
| "parentgiving.c…" under a candidate | parentgiving.com | `text.s.mid` | drop the cap for this label, the slot is 139 px wide |
| "4.8 · None", "5 · 2", "3.9 · 28" | rating and number of reviews | `text.l.mid` | "4.8 ★ · 28 reviews"; nothing when null |
| Bottom strip: "1 outside ▪ 1 not stated ▫ 11 outside … 2 unclear … 19 not stated" next to rows of blurred 8 px thumbnails | 34 rejected, grouped by reason | `text.gs` | one lead word: "34 rejected:" and "outside" → "too wide" |
| Our words: "measured / 1 h 23 min", "11 things remembered / open to read", "What it already knows · 11 memories recalled, of 49 held.", "Replay of this run's records · 3 h 1 min of work · 3 of 11" | | `explore.js` | "measured 1 h ago"; the rest can stay |
| First 10 seconds: the right 40 % of the overlay is empty and the left column is 12 px text | | | acceptable; the headline (20 px) carries it |

### `/seal/` (web/seal)

| Shown | Issue | Element, file | Fix |
|-------|-------|---------------|-----|
| "Who holds what": "private key · made on the phone, never leaves it", "can check a signature, cannot make one" | cut by the fold at 810 (y = 795 to 837); the event log under it is never seen | `.lg.head .lane`, `seal.css` | scroll in the video, or move this card above "Try to get a cart" |
| "sign the sheet · no signature" next to "Ask for carts with no signature" | reads as an instruction, it is the request that was sent | `.try .sent`, `seal.css:109` | "asks for carts · unsigned" |
| "401 · 15:43:35", "409 · …" | status codes | `.try .got` | drop the code, keep the time |
| "A signature over the cart covers 7 of 23 rows" | unclear whose signature | `#cartview.cv` | "A checkout signature would cover 7 of 23 rows" |
| "✓ SHA-256 recomputed ✓ ECDSA P-256 signature", "One fingerprint · SHA-256 of every row" | jargon, fine for judges, 12 px | | leave |
| Event log: "signed persona_start", "identity inquiry created · sandbox", "cart gate closed: no signature" | internal names | `seal.js` event labels | "asked for an identity check", "identity check passed", "no cart: nothing signed" |

### `/phone/` (web/phone/index.html)

| Shown | Issue | Fix |
|-------|-------|-----|
| "Sign" button at y = 1122 (y = 1292 when an ask is open) on an 844 px screen; "check identity" link at y = 844, exactly under the tab bar | the one action is off screen | `#sign { position: sticky; bottom: 64px; }` |
| "overall width passes the door 28 in · from the / home" | one word wraps alone (`.lim`) | "· home" / "· order" instead of "· from the home" / "· from the order" |
| Header pill "Dana · key 0007e1" | internal | "Dana's phone" |
| Tabs "Sheet · Items · Adjust a limit" | "Sheet" is our word | "Sign · Remove an item · Adjust a limit" |
| "Pick rule: cheapest that meets the order" | internal (`index.html:319`) | "Chosen: cheapest that meets the order" |
| "Total in carts $114.69" before any cart exists | wrong tense | "Total" |
| "identity not checked · needed to sign · check identity", "Live human check (sandbox) · open", "Sentences", tags "advisory" / "conflict", "6 of 7 verified, 1 stop the signature" (yet Sign is enabled) | internal, and the last one contradicts the button | hide "Live human check" for the video; "1 differs from the order" (the signed screen already says this) |
| "What you sign · e374 c2ec dab0" | no word that this is the same code as on the laptop until the line below | "Fingerprint, same as on the laptop" as the caption |
| Signed screen headline "Dana (identity checked, sandbox)" | the headline should be the event | "Signed by Dana" |
| Enrol screen: "Enrol this phone", "Name on the seal", "Code from the laptop" | "enrol", "seal" | "Set up this phone to sign", "Your name" |

### Other tabs, first screen only (shots `live-tab-*.png`)

| Page | Shown | Element, file | Fix |
|------|-------|---------------|-----|
| Trail | "weight capacity: how much weight the item holds: the heaviest person it is made to carry, …" cut to 1 line of 5 | `p.pg.one`, `web/trail` | clamp 2 |
| Trail | "Adjustable Height Bathing Stool by Dri…" | `.fc.rowc .tt`, `web/trail` | `white-space: normal` |
| Trail | Draft message "My mother, who weighs 280 lbs and recently had hip surgery, needs a Deluxe Aluminum Bath B…" cut at 3 lines of 6 | `#fl-draft p.dr`, `web/trail` | clamp 6: this is the privacy point, it must be readable |
| Trail | "carex.com on returns: "Opened bath seats cannot be return…", "carex.com on delivery: "Standard shipping is 3–5 …" | `.fl-mem p.mi`, `web/trail` | `white-space: normal` |
| Conversations | "A store's agent may receive: product name · need-by date · delivery region. Never: order l…" (the rule itself is cut) | `#band .rule`, `web/talk/talk.css` | `white-space: normal` |
| Memory | no cuts found on the first screen | | |

## B. As a stranger

1. `/` first look. Expected: a title telling me what was decided and for whom. Got: a dense, tidy table for "Shower chair" with two rows and a row of seven steps. I understood "an agent compared products against limits". I did not know who Dana or Elena are, or that the therapist and Dana are the same person.
2. Clicked Walker, Grab bar. Expected and got: the table changes. Clear. The left card is the best part of the screen (the sentence with the number highlighted).
3. Clicked a rejected row. Expected: why it was rejected. Got: the right card changes to that product with the failing line. Clear, but nothing on the row says it can be clicked.
4. Clicked the Recommended row. Got the same card as at the start. Fine.
5. "Replay the run". Expected: a video of the search. Got: an overlay that builds a graph for 35 seconds and stops on "Nothing is bought until Dana signs." This is where I learned the story: Rosa's hip replacement, Elena the daughter, Dana the occupational therapist. That belongs on the first screen, in one line. Lost at: the bottom strip of blurred thumbnails, "4.8 · None".
6. "Ask Dana". Could not find it. It is behind the 11 px "Dana's limit" in the column header. Once open: "Elena proposes; Dana decides on the phone." One good line. It replaces the Recommended and Signature cards, which is fine.
7. Signature card. Expected: a button. Got: a QR and "Scan to enrol the phone". I did not know who scans, or that scanning is the next step.
8. `/phone/`. Expected: "Dana, review and sign". Got: three cards and no visible action; Sign is one and a half screens down. First tap changes the button to "Tap again to sign"; no other feedback.
9. After signing, `/`: pill "Signed", steps 6 and 7 ticked ("Carts · 2 created"), the Signature card lists two cart links. The centre of the screen does not change at all.
10. `/seal/`. Clear headline sentence, the edit turns the fingerprint red, the four attempts are refused in place. The strongest page for a judge. The lanes under the fold are lost.

| Question | Answer | Smallest change |
|----------|--------|-----------------|
| 1. Who is looking at this screen? | No | Top bar line (row 2 of the top ten): "Elena, daughter, at the house, shops · Dana, occupational therapist, signs". |
| 2. What are the three people to each other? | No on `/`; yes inside the replay | Same line. Left card caption "Dana's limits" → "Dana's order for Rosa" if the sheet carries the patient's name; otherwise "Dana's order". |
| 3. What happened before I arrived? | Yes, the step row says it (List read → Stores searched → Pages read → Checked → Picked) | Only: "List read" → "Order read" (the phone and the table call it "the order"). |
| 4. What am I supposed to do next? | No | Step 6 small text "next · on her phone"; Signature card "Next: Dana scans this to sign" (row 7). |
| 5. What is the phone for? | No | h1 "Dana signs · Home after surgery", sticky Sign button, tab "Sign" (row 5). |
| 6. What changed after signing? | Half: only the edges change | Signature card first line "Signed by Dana · 2 carts made"; when signed, put the Signature card above the Recommended card (order of elements in `#side`). |

Also seen: after Dana's change the left list still says 300 lb (row 9). On the live instance the recommended shower chair is from parentgiving.com while the replay shows "amazon.com" under it (row 4).
