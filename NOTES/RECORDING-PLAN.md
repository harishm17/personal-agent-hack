# Recording plan

Written 14:50 from a run of the product on a replay copy (port 8032, since removed) and GET-only looks at
main (8800). Record 15:30 to 16:10, assemble 16:10 to 16:25, submit by 16:30. Numbers in captions are read
from the screen on the day; the ones below are what the screen showed at 14:45.

## What I saw, and what it changes

| Seen | Consequence |
|---|---|
| The phone flow works end to end on a copy: enrol with the code, drag "shower chair holds at least" from 300 to 375, the laptop's limit counts up, four rows turn red, the pick moves ("was picked" on the old row, "now at carex.com" on the panel), two taps, "Signed by Dana" and two cart lines about 4 s later. | This is the centre of the video. One continuous take. |
| Signing is refused while the phone says "identity not checked · needed to sign" (the identity gate is on by default). | The identity check must be done before the take. It needs the phone's camera or the laptop's rehearsal control; see 1.3. |
| `POST /api/admin/reset` clears the key, the identity check and makes a new code. | Every retake of the signing take costs a new enrolment and a new identity check. Rehearse on a copy; sign on main once. |
| The trail replay goes back to step 1 when a record arrives while it plays (seen just after signing). With `/trail/?live=0` it played all seven steps in 24 s. | Record the replay at `/trail/?live=0`. |
| Clicking an item on the decision screen re-checks its rows top to bottom in about a second. | Free motion on real data: start each decision shot with the click. |
| At 14:47 main has no ordering control, `/graph/` is the still graph of one decision, and `/seal/` answers 404. | Shots 4, 7 and 11 are "lands by 15:20", each with a substitute. Look again at 15:20. |
| The decision screen holds at a 1338-wide window (names are cut shorter); at 1728 it has room. | Two window arrangements: full stage for laptop shots, split for the phone take. |
| This Mac: ffmpeg 9 is installed but has no text filter (`drawtext`, `subtitles` both absent); iMovie is not installed; QuickTime Player, Screenshot and iPhone Mirroring are. | Captions are drawn by Chrome and laid under the picture by `demo/recording/make.sh` (tested). |
| The agent's draft on the trail reads "My mother, who weighs 280 lbs"; DEMO.md's opening says "His therapist … his daughter". | Pick one before recording; the captions here name no gender. |
| `demo/` has no video recorder. `shot.sh` takes stills, `frames.mjs` takes frame series for checking motion, `contact.sh` tiles them, `signer.py` plays the phone from the laptop on a dev port. `shots.example.json` describes another product and nothing here reads it. | They still fit for checking a page. They do not make the video. `signer.py` was not run today by me. |

## 1. Setup with iPhone Mirroring

### 1.1 The stage (16:9)

The display is 3456 x 2234. At the default scaling that is 1728 x 1117 points; confirm in System Settings >
Displays (the middle choice, "Default"). All sizes below are points at that scaling.

- **Stage:** 1728 x 972, from x 0 to 1728 and y 44 to 1016. The menu bar stays above it. Hide the Dock (⌥⌘D).
- **Backdrop:** one Chrome window filling the stage with the page colour, so no desktop shows in a gap.
- **Arrangement A, laptop shots:** the product window fills the stage.
- **Arrangement B, the phone take:** product window 1338 wide on the left; the phone column is the right 390,
  with the iPhone Mirroring window centred in it.

```sh
# backdrop (run once)
osascript -e 'tell application "Google Chrome"
  set w to make new window
  set URL of active tab of w to "data:text/html,<title>.</title><body style=background:%23f7f8fa>"
  set bounds of w to {0, 44, 1728, 1016}
end tell'
# product window, arrangement A (use B's numbers {0, 44, 1338, 1016} for the phone take)
osascript -e 'tell application "Google Chrome"
  set w to make new window
  set URL of active tab of w to "http://localhost:8800/"
  set bounds of w to {0, 44, 1728, 1016}
end tell'
# switch the front Chrome window between A and B
osascript -e 'tell application "Google Chrome" to set bounds of front window to {0, 44, 1338, 1016}'
```
Not run on this screen (it would have opened windows on the builder's desk). First run asks once to let the
terminal control Chrome. In Chrome: View > uncheck "Always Show Bookmarks Bar"; one tab per window, so the
tab strip is quiet. The address bar showing `localhost:8800` is true and can stay.

**The phone window.** iPhone Mirroring cannot be resized freely; the View menu has three sizes (Smaller,
Actual Size, Larger: ⌘−, ⌘0, ⌘+). I do not know their pixel sizes for this phone. One-minute test: open it,
press ⌘⇧4 then Space, click the window with ⌥ held (no shadow), open the picture in Preview, ⌘I, halve the
pixel size. Use the largest size that is at most 390 wide and 972 high; drag it to the middle of the right
column. If even "Smaller" is wider than 390, give the phone 432 and the product window 1296.

### 1.2 Recording tool and steps

Use the built-in recorder with a selected region (⌘⇧5). QuickTime Player > File > New Screen Recording opens
the same toolbar, so there is nothing to choose between them.

1. ⌘⇧5 > "Record Selected Portion". Drag the frame onto the stage; the size shows while dragging: 1728 x 972.
   A few points off is fine (the script fits and pads). The frame is remembered for the next take.
2. Options: Save to Desktop; Timer None; Microphone None; "Show Mouse Clicks" on (each click draws a ring,
   which is how a tap in the phone window becomes visible); "Remember Last Selection" on.
3. Record. Stop with ⌘⌃Esc or the stop square in the menu bar. Dismiss the thumbnail; the file is
   `Screen Recording … .mov` on the Desktop.
4. Turn on Do Not Disturb on the Mac before the first take (Control Centre > Focus).
5. Leave two still seconds at the start and end of every take; move the pointer slowly; rest it off the text.

### 1.3 What iPhone Mirroring cannot do here, and the way round each

| Limit | Sure? | Way round |
|---|---|---|
| The camera does not work in a mirroring session, so the QR code cannot be scanned inside it. | Yes (Apple says camera and microphone are unavailable). | Either scan with the phone in hand before mirroring (the key stays in Safari; mirroring then shows the enrolled page), or enrol inside the mirror by pasting the link: `curl -s localhost:8800/api/issuer/enroll-code \| python3 -c "import json,sys;print(json.load(sys.stdin)['url'])" \| pbcopy`, then in the mirrored Safari click the address bar and ⌘V. The second way lets the video show the "Enrol this phone" tap. |
| Pasting from the Mac into the mirrored phone. | Fairly sure it works (shared clipboard; Handoff on, same Apple Account). | Test once. If it fails: type the address by hand with the Mac keyboard; the code is six characters. |
| The identity check (Persona's page wants the camera). | The camera limit is sure; whether Persona's sandbox page lets you pass without a camera I do not know. | Do it with the phone in hand before mirroring; or tap "check identity" in the mirror and approve from the laptop: `curl -s -X POST localhost:8800/api/admin/persona/simulate -H 'content-type: application/json' -d '{"action":"approve"}'`, then tap "refresh" on the phone. I did not run this (it calls Persona's sandbox). The seal then reads "identity checked (sandbox)"; with `PERSONA_REQUIRED=0` it reads "self-declared". Either is true; say what it reads. |
| The key belongs to one browser and one address. | Yes (seen: the page says so, and the tunnel script says keys are per address). | Enrol in Safari itself, not a private tab and not a scanner app's built-in browser, and at the tunnel address the laptop's QR shows. Do not restart the tunnel after 15:20. |
| The phone must be locked and near the Mac; picking it up and unlocking it ends the session. | Yes. | Phone face down, on power, next to the Mac. Never touch it during the take. To use it by hand again, just unlock it; to mirror again, lock it and click Connect. |
| Both devices need Wi-Fi and Bluetooth on and the same Apple Account; the first connection asks for the phone's passcode and the Mac's password or Touch ID. | Yes. | Connect once at 15:25, choose "authenticate automatically". |
| The Mac must not be using AirPlay or Sidecar. | Yes. | Matters at 17:00 only if the projector is on AirPlay. Cable, or no mirroring. |
| The Mac getting its internet from this phone's Personal Hotspot. | Not sure; I believe mirroring is refused or drops. | Test at 15:25: with the hotspot feeding the Mac, open iPhone Mirroring. If it will not connect, record on the venue Wi-Fi. |
| A session left idle. | Not sure; I believe it pauses after some minutes. | Open the mirror just before the phone take. If it shows a paused card, click Connect. |
| Phone notifications show on the Mac as banners. | Yes. | Do Not Disturb on the Mac (1.2 step 4) and a Focus on the phone. The phone page itself sends none. |
| Sound. | The phone's sound plays through the Mac; the page makes none. The built-in recorder takes the microphone only. | Microphone None. Voice, if any, is one separate recording laid under the whole video (`VOICE=`). |
| Whether the recorder captures the mirror window at all. | Believed yes (it is an ordinary window; only protected video is blanked). Not tested here. | The first thing to test at 15:25: record five seconds of the mirror and play it. If it is black, use the fallback below. |
| Dragging the slider. | Believed yes: press and drag is a touch drag. | Rehearse the drag in the mirror on "Adjust a limit" until it lands on 375 first time (steps of 25; 350 does not move the pick, 375 does). |

### 1.4 Fallback with no phone

A second Chrome window on `/phone/`, 390 x 844, in the right column (DEMO.md lists this as seen working; I
enrolled, changed a limit and signed this way on the copy).

```sh
open -na "Google Chrome" --args --user-data-dir=/tmp/signoff-phone --app="http://localhost:8800/phone/" \
  --window-size=390,872 --window-position=1338,94
```
The separate profile is the "phone": its key lives there, so enrol and sign in this window only. Paste the
code from the laptop's signature block. If Chrome will not make a window narrower than 500 (not sure), open
`/phone/` in a normal window, DevTools > device toolbar (⌘⇧M) > 390 x 844 at 100%, and let the cut's zoom
crop to the device. The caption for this shot must not say "phone" if no phone is on screen: say "the
approver's page" and keep "phone" for the real take.

## 2. Shot list (2:30)

One caption per shot, in the band under the picture. Voice lines are optional and say the same thing.
Zoom is the script's `cx,cy,k`. "Now" means I saw it work at 14:45; "15:20" means it was not on main then.

| # | Time | Page and state | Action | Eye on | Caption | Voice | Zoom | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | 0:00 to 0:05 | Card | none | the words | A therapist wrote what the house needs. / Her patient's daughter shops. / Neither can pick the product alone. | "A patient comes home after surgery. The therapist wrote the order; the daughter shops." | card | now |
| 2 | 0:05 to 0:22 | Decision, sheet 4, unsigned | Click **Grab bar**: the rows are checked top to bottom. Rest the pointer on the fold line. | the red figures; "lowest 75 lb" in the fold line | The order says 300 lb. 18 cheaper grab bars are rejected, each with its reason. | "Cheapest first. Eighteen cheaper bars are rejected. One states 75 pounds; her order says 300." | first 5 s whole frame, then `0.45,0.42,1.5` | now |
| 3 | 0:22 to 0:30 | same | none | the top row: "unclear · option says 36 in, page describes 12, 16, 24 in" | The page does not describe this size. Unclear is not bought. | "Sold as 36 inch on a page that describes other sizes. Unclear means not bought." | `0.45,0.35,1.8` | now |
| 4 | 0:30 to 0:46 | `/graph/`, Play | Press Play once | products appearing as nodes; a rule setting the failing ones aside | Every product found, and the rule that set each one aside. | "Each product it found, and the rule that sets it aside, with the reason." | whole frame | 15:20. Substitute: Decision, click **Shower chair** (rows checked again, "42 read"), 8 s, then today's `/graph/` still for 8 s with "One decision as a graph: who said what, and which words decided it." |
| 5 | 0:46 to 1:04 | `/trail/?live=0`, Play | Press Play; let steps 1 to 5 run | the store page entering "What the model sees"; the two limits going round it under "never enters a model call" | The model gets one page of store text. Her limit and the tub's width go round it; code compares them. | "This is all the model gets: one page. The limit and the measurements never go in. Code compares." | whole frame; `0.5,0.45,1.3` once the frame is full | now |
| 6 | 1:04 to 1:12 | same replay, the guard row (the page scrolls to it at step 6) | none | the struck chips beside "Guard · stopped here" | Asking the store's agent about returns: the guard stops the weight, the surgery, the limit and the names. | "When our agent asks the store's agent, the guard stops what is private." | `0.5,0.8,1.5` | now |
| 7 | 1:12 to 1:20 | Decision, ordering control | Click "Best reviewed", then back to "Cheapest" | the "Recommended" row moving | Among those that pass, the shopper chooses the ordering. The rules stay the therapist's. | "The shopper picks the ordering; she cannot change the rules." | `0.45,0.4,1.4` | 15:20. Substitute: drop it; give 4 s each to shots 9 and 10. |
| 8 | 1:20 to 1:30 | Arrangement B. Laptop: Decision > Shower chair, the QR and code in the signature block. Phone: "Use this phone to sign", code filled. | Tap **Enrol this phone** | the phone, then "Phone enrolled" on the laptop | She enrols her phone with a one-time code. The key is made in the phone's browser and stays there. | "The therapist enrols her phone. The key never leaves it." | first half `0.88,0.5,1.6`, then whole frame | now |
| 9 | 1:30 to 1:45 | Phone: Adjust a limit > shower chair holds at least. Laptop: Shower chair. | Drag the slider from 300 to 375 | on the laptop: the limit counting up, figures turning red, "was picked", "now at carex.com" | She raises her limit to 375 lb. The pick moves to another store. | "She raises her limit from her phone. The pick moves." | whole frame; no zoom, both sides must be seen | now |
| 10 | 1:45 to 2:00 | Phone: Sheet, scrolled to **Sign**. Laptop: same. | Tap Sign, then "Tap again to sign"; wait for the carts (about 4 s) | the signature block: "Signed by Dana", then the two cart lines | Two taps. Only now do carts exist, at the stores. Nothing is checked out. | "She signs. Only now do carts exist. Nothing is checked out." | whole frame, then `0.87,0.75,1.8` on the signature block | now |
| 11 | 2:00 to 2:17 | `/seal/` (signed) | Use "change one thing": edit one value | the fingerprint changing and the check failing | Her signature covers every rule, quote, pick and price. Change one value and it no longer verifies. | "She signed the reasons, not just a total. Change one value and the check fails." | whole frame, then zoom on the failed check | 15:20. Substitute: the phone's "What you sign" line ("Computed on this phone from the sheet above; the server's hash is the same") before the taps in shot 10, and the laptop's "Sheet hash · Hash covers limits, strikes, picks" after; caption "She signs one fingerprint of the rules, quotes and picks." |
| 12 | 2:17 to 2:24 | Title menu > Room 12 class supplies > Headphones (record last: it starts a new run) | Click Headphones | "95 dB, over 85" | Same engine, a teacher's list: this headphone states 95 dB; the order says 85. | "Same engine, a teacher's list." | zoom on the row | now per DEMO.md; I did not open sheet 3. Drop first if time is short and give the seconds to 11. |
| 13 | 2:24 to 2:30 | Card | none | the words | The people are invented. / The stores, pages, prices and carts are real. / Nothing is checked out. | "The people are invented; the stores, pages, prices and carts are real. Sign-Off." | card | now |

Rules for the words: "states", never "proves"; a count only if it is on the screen in that shot; "carts at
the stores" only if the take was signed on main in live mode (a replay copy labels its carts "replay", and
then the caption is "Two taps, and the carts appear").

### Takes, in this order (state decides the order)

| Take | Arrangement | State | Shots | Seconds of recording |
|---|---|---|---|---|
| a | A | main, unsigned, phone not enrolled | 2, 3, 7 (set the ordering back to Cheapest after) | 60 |
| b | A | same | 5, 6 at `/trail/?live=0`; 4 at `/graph/` | 90 |
| c | B | enrolment link ready, identity plan chosen | 8, 9, 10 in one go | 60 |
| d | A | signed | 11 | 40 |
| e | A | last | 12 (the sheet switch wipes the signed run) | 20 |

Rehearse take c twice on a copy first (`SIGNOFF_MODE=replay … --port 8032` in a temp worktree, with the
fallback phone window pointed at 8032), then do it once on main. If it goes wrong on main after signing:
reset, enrol again, identity again, about three minutes. Decide before 15:55 whether there is time.

## 3. Assembly in 15 minutes

`demo/recording/make.sh <clips-folder> <cuts-file> [out.mp4]` trims, zooms, joins, draws the captions in
the band under the picture and the cards, adds a silent sound track, and keeps the file under `MAXMB` (95 by
default). Tested at 14:43 on two dummy clips of different sizes and frame rates: cards, a caption, a wrapped
caption, a zoom, a 2x cut and the second encode for the size limit all came out right. The real `cuts.txt`
run on five dummy clips gave 16 cuts, 2:30 exactly, in 19 s.
Output is 1920 x 1080, 30 frames a second, H.264 with AAC, playable from the first byte.

1. `mkdir -p demo/out/clips && mv ~/Desktop/Screen\ Recording*.mov demo/out/clips/` and rename them
   `a.mov` to `e.mov` in take order (`demo/out/` is ignored by git).
2. Open each in QuickTime Player, scrub, and write each shot's in and out seconds into
   `demo/recording/cuts.txt` (the captions are already there). Four minutes.
3. `demo/recording/make.sh demo/out/clips demo/recording/cuts.txt demo/out/sign-off-demo.mp4`
   It prints each cut, the length and the size, and warns over 3:00. About one minute.
4. Watch it once at full size. Fix a time or a word in `cuts.txt`, run again.
5. Voice, if recorded: QuickTime Player > File > New Audio Recording while the silent video plays, save as
   `voice.m4a`, then `VOICE=demo/out/voice.m4a demo/recording/make.sh …`.
6. Size: my guess is 15 to 40 MB for 2:30 of screen (not measured on a real take; a noisy test pattern
   gave 92 MB). The script prints the size. If the form's limit is lower, `MAXMB=24 demo/recording/make.sh …`.
   For an unlisted link, upload by 16:15: processing to HD takes minutes after the upload ends.

By hand, if the script fails:
```sh
ffmpeg -ss 12 -to 27 -i a.mov -vf "scale=1920:-2,fps=30" -c:v libx264 -crf 20 -pix_fmt yuv420p -an 02.mp4   # one cut
printf "file '%s'\n" 0*.mp4 > list.txt && ffmpeg -f concat -safe 0 -i list.txt -c copy -movflags +faststart out.mp4
```
QuickTime alone: Edit > Trim (⌘T) on each clip, Edit > Add Clip to End, File > Export As > 1080p. It cannot
draw captions; then the captions must be said aloud or the cards carry the story.

## 4. The live three minutes, as a delta from the video

- **The phone is in the hand, not mirrored.** A phone in use cannot be mirrored, and a judge can be handed it.
  Enrol by scanning the QR at 16:50 as DEMO.md says; identity check done then too.
- **No cards, no zooms.** Say the opening and closing lines from DEMO.md. Browser zoom 125% (150% if the room
  is deep); arrangement A.
- **Drop** shot 12's sheet switch unless there are twenty seconds left, and shot 7 unless it was rehearsed.
  Keep 4 and 11 only if they landed and were run twice; otherwise their substitutes.
- **By hand:** click Grab bar; press Play on the trail; drag the limit on the phone; two taps; open the seal.
- **Tabs, left to right, all loaded before walking up:** 1 Decision (`/`, Shower chair selected last so the
  phone beat needs no click) · 2 Trail (`/trail/?live=0`, at step 1) · 3 Graph (`/graph/`) · 4 Seal (`/seal/`,
  reload it after signing) · 5 the backup clip, open in QuickTime in another Space, paused on its first frame.
- **Order:** 1 (order, grab bar, unclear) → 2 (replay, guard) → 3 (graph, 15 s) → 1 (phone: limit, sign,
  carts) → 4 (seal, change one thing) → close on tab 1 with the carts on screen.
- Tab 2 was loaded before signing and has no event stream, so it shows "not signed": do not go back to it.

## 5. Before recording (15:25)

- [ ] Main at 15:20: look at `/graph/`, `/seal/` and the ordering control; mark shots 4, 7, 11 real or substitute.
- [ ] Displays on Default (1728 x 1117); Dock hidden; Do Not Disturb on; bookmarks bar off; one tab per window.
- [ ] Backdrop and product window placed (1.1); ⌘⇧5 frame on the stage, Microphone None, Show Mouse Clicks on.
- [ ] Five-second test recording of the iPhone Mirroring window plays back with a picture; window size chosen.
- [ ] Tunnel up and not to be restarted; `POST /api/admin/reset` done; main shows sheet 4, unsigned.
- [ ] Enrolment link on the clipboard; paste into the mirrored Safari works; identity plan chosen (1.3).
- [ ] Take c rehearsed twice on a replay copy; the slider lands on 375 first time.
- [ ] `/trail/?live=0` plays to step 7 without jumping back.
- [ ] `demo/out/clips/` exists; `demo/recording/cuts.txt` open; phone face down, locked, on power.
- [ ] Title menu untouched until take e.
