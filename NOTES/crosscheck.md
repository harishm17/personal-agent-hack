
## 11:33 e6f5f26-SIGN-Senso-document-loading-sentence-che
- [ ] SIGN `signoff/sign/senso.py:38` By default only `conflict` blocks a signature, and store sentences never block (STORE_BLOCKS is off). CONTRACT.md says conflict or unsupported blocks the signature, so the default does not match it. Fix: Block on both conflict and unsupported by default, and get an integrator amendment if the judge is too unreliable for that.
- [ ] SIGN `tests/sign/test_requests.py:186` The test that asserted a 'supported' verdict still signs was replaced. The new test asserts that an 'unsupported' blocking sentence signs, which locks in the weakened gate. Fix: Keep a test that unsupported blocks, and move the opt-out behaviour to its own clearly labelled test.

INTEGRATOR 11:40: both items settled by contract Amendment 11:40 (order sentences block on conflict or unsupported; limit sentences are advisory by design).
