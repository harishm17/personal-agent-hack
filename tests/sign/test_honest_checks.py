"""The phone and the seal say a check happened only when a verdict for the signed hash exists (G19)."""
import json
import pathlib
import subprocess

from signoff.sign import api, persona, senso

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def text_for(signature, word="order"):
    html = (ROOT / "web" / "phone" / "index.html").read_text()
    fn = html.split("/* senso-seal-text:start */")[1].split("/* senso-seal-text:end */")[0]
    out = subprocess.run(["node", "-e", fn + "\nconsole.log(JSON.stringify(sensoSealText(%s, %s)))" % (json.dumps(signature), json.dumps(word))],
                         capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def sign(env):
    return env.client.post("/api/issuer/request", json=env.phone.request("sign_sheet", sheet_hash=env.engine.sheet_hash()))


def test_senso_not_connected_is_signed_as_not_checked(env):
    r = sign(env)
    assert r.status_code == 200 and r.json()["senso"] == "not_connected"
    sg = env.engine.state["seal"]["signature"]
    assert sg["senso"]["status"] == "not_connected" and sg["senso"]["label"] == "not checked: Senso is not connected"
    assert text_for(sg) == "not checked: Senso is not connected"
    assert "Checked against" not in text_for(sg)


def test_senso_on_but_not_answering_is_signed_as_unavailable(env, monkeypatch):
    monkeypatch.setattr(senso, "configured", lambda: True)
    monkeypatch.setattr(api, "ensure_watcher", lambda: None)
    senso._meta["error"] = "ConnectError"
    monkeypatch.setattr(api, "SENSO_WAIT_S", 0.3)
    r = sign(env)
    assert r.status_code == 200 and r.json()["senso"] == "unavailable"
    sg = env.engine.state["seal"]["signature"]
    assert sg["senso"]["status"] == "unavailable" and "not reachable" in sg["senso"]["label"]
    assert text_for(sg) == "not checked: Senso not reachable"
    senso._meta["error"] = None


def test_a_run_that_is_still_going_is_signed_as_running(env, monkeypatch):
    monkeypatch.setattr(senso, "configured", lambda: True)
    monkeypatch.setattr(api, "ensure_watcher", lambda: None)
    monkeypatch.setattr(api, "SENSO_WAIT_S", 0.3)
    sign(env)
    assert text_for(env.engine.state["seal"]["signature"]) == "Senso check still running"


def test_checked_is_said_only_for_a_verdict_that_exists_and_names_the_version():
    rows = [{"verdict": "verified", "source": {"version_id": "v1abcdef12", "version_num": 3}},
            {"verdict": "verified", "source": {"version_id": "v1abcdef12", "version_num": 3}}]
    assert text_for({"senso": {"status": "complete", "checks": rows}}, "list") == "Checked against the list (version 3): 2 of 2 verified"
    rows.append({"verdict": "error"})
    assert "1 not checked (Senso did not answer)" in text_for({"senso": {"status": "complete", "checks": rows}})
    assert text_for({"senso": {"status": "complete", "checks": []}}) == "nothing to check against the order"
    assert text_for({}) == "not checked: no Senso result on this signature"
    assert text_for({"senso": {"status": "weird"}}) == "not checked"


def test_identity_is_never_implied(env):
    sign(env)
    sg = env.engine.state["seal"]["signature"]
    assert sg["name_basis"] == "self-declared" and sg["persona"]["label"] == "identity not checked" and not sg["persona"]["verified"]
    html = (ROOT / "web" / "phone" / "index.html").read_text()
    assert '"identity not checked"' in html                      # the phone's fallback is the plain statement


def test_a_sentence_that_differs_or_is_unsupported_is_counted_not_hidden():
    rows = [{"verdict": "verified"}] * 5 + [{"verdict": "conflict"}, {"verdict": "unsupported"}]
    assert text_for({"senso": {"status": "complete", "checks": rows}}, "list") == \
        "Checked against the list: 5 of 7 verified, 1 differs from the list, 1 not supported by the list"
