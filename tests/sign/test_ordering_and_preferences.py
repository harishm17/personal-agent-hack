"""G22: the phone names the ordering the shopper chose and lists preferences as preferences; a changed ordering is caught
by the hash the phone signed."""
import json
import subprocess

from signoff.engine import state as engine_state

from .conftest import _make_env
from .sheet4_state import build
from .standin import ROOT, FakeEngine


def phone_js(expr, state, canon_rule=None):
    html = (ROOT / "web" / "phone" / "index.html").read_text()
    fn = html.split("/* ordering-and-preferences:start */")[1].split("/* ordering-and-preferences:end */")[0]
    prelude = ("const esc=(s)=>String(s??'').replace(/[&<>\"]/g,'');const fmt=(v)=>String(v);const OPS={'>=':'at least','<=':'at most'};"
               "const LIM=()=>'limit';let state=%s;const shopperName=()=>state.sheet.shopper.name;" % json.dumps(state))
    out = subprocess.run(["node", "-e", prelude + fn + "\nconsole.log(JSON.stringify(%s))" % expr], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


STATE = {"sheet": {"shopper": {"name": "Elena"}, "pick_rule": {"id": "best_reviewed", "label": "the best reviewed that passes", "set_by": "Elena"},
                   "lines": [{"preferences": [{"id": "C3.sheets", "label": "at least"}]}]}}


def test_the_phone_says_who_asked_for_the_ordering():
    assert phone_js('ruleText({pick_rule:{id:"best_reviewed",label:"the best reviewed that passes"}})', STATE) == \
        "Elena asked for the best reviewed that passes"


def test_it_does_not_claim_a_choice_the_state_does_not_show():
    other = json.loads(json.dumps(STATE))
    other["sheet"]["pick_rule"]["id"] = "cheapest"          # the state names another rule than the signed sheet
    assert phone_js('ruleText({pick_rule:{id:"best_reviewed",label:"the best reviewed that passes"}})', other) == \
        "Pick rule: the best reviewed that passes"
    other["sheet"]["pick_rule"] = {"id": "best_reviewed", "label": "x", "set_by": "shopper"}   # the sheet's own rule, not her choice
    assert phone_js('ruleText({pick_rule:{id:"best_reviewed",label:"the best reviewed that passes"}})', other).startswith("Pick rule: ")


def test_a_preference_reads_as_a_preference_and_is_not_a_button():
    html = phone_js('prefRowC({id:"C3.sheets",op:">=",bound:100,unit:"sheets",terms:["sheet_count"],set_by:"shopper"})', STATE)
    assert "prefers at least" in html and "100 sheets" in html and "a preference, not a limit" in html
    assert html.startswith('<div class="pref">') and "<button" not in html and "data-lim" not in html


def test_a_changed_ordering_after_she_looked_is_refused_by_the_hash(monkeypatch):
    class Real(FakeEngine):
        def canonical_sheet(self):
            return engine_state._canonical(self.state)

    env = _make_env(monkeypatch, Real(build), "sheet4")
    looked_at = env.engine.sheet_hash()
    env.engine.state["sheet"]["pick_rule"] = {**env.engine.state["sheet"]["pick_rule"], "id": "best_reviewed", "label": "the best reviewed that passes"}
    assert env.engine.sheet_hash() != looked_at                         # the ordering is under the hash
    r = env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=looked_at))
    assert r.status_code == 409 and r.json()["error"] == "stale_hash"
    assert env.cart.calls == [] and not env.engine.state["seal"]["signed"]


def test_a_preference_sentence_in_the_order_does_not_move_the_requirement_sentences(monkeypatch):
    """Sheet 3's order with "100 sheets if they have them" added, once under item 3 and once inside the limits block: the
    sentences sent to Senso are the same eight, all in the document's own words."""
    from signoff.sign import senso
    from .sheet3_state import build as build3
    base = (ROOT / "sheets" / "sheet3_order.txt").read_text()
    requirement = "Our order requires the notebook to have at least 70 sheets.\n"
    added = "It must have at least 70 sheets. 100 sheets if they have them."  # under item 3 (the real file has it since 14:55)
    variants = [base if added in base else base.replace("It must have at least 70 sheets.", added, 1),
                base.replace(requirement, requirement + "Our order prefers 100 sheets if they have them.\n", 1)]
    want = [r["sentence"] for r in senso.sentences_for(build3())]
    for text in variants:
        monkeypatch.setattr(senso, "_order_text", lambda sheet, text=text: text)
        rows = [r["sentence"] for r in senso.sentences_for(build3())]
        assert rows == want and all(s in text for s in rows)
