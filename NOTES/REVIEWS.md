
## 14:37 from ENGINE — how the engine calls `ratings` (E30, E32), so R4 fits first time
- The engine looks for `signoff.reviews.ratings`, then `signoff.reviews.reviews.ratings`, on every recompute, and calls
  `ratings(line_id)` once per line. It wants `{candidate_id: {"rating": 4.8, "out_of": 5, "review_count": 212}}`, cache only.
  On my branch at 14:37 neither name exists yet, so every product is unrated and each line says so.
- While you answer, `engine.get_state()` returns this version's candidates (ids, status, product), built without ratings and
  without the keys the engine attaches later (`sheet_hash`, `two_readers`, …); read `lines[].candidates[]` only. Return every
  candidate you hold a rating for, passing or not: the engine orders only those that pass.
- A rating is ordered only when `out_of` is a number (it is compared as a share of its scale; 9 of 10 is 4.5 of 5). With
  `out_of` missing the rating is not ordered and not shown; its `review_count` still counts for `most_popular`. Please do not
  fill in a scale the page did not state.
- It must not raise and must not use the network: an exception is caught, all products are shown as unrated, and the state says
  so in `degraded` ("ratings"). It runs inside every recompute, so it should take a few ms.
