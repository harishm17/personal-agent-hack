"""M4, a second run shown: run a sheet, change a home measurement, strike a product as the approver with a reason,
sign; reset; then read what the new run starts with. Talks to the app over HTTP as the laptop and the phone do.

    SIGNOFF_MODE=replay SIGNOFF_SHEET=sheet4 PERSONA_REQUIRED=0 uv run uvicorn signoff.app:app --port 8007
    uv run python -m tests.memory.second_run            # saves data/memory/second_run/run1.json and run2.json

Nothing here writes a memory: the script only does what a shopper and an approver do, and the memories come from
the receipts those actions leave."""
import datetime
import json
import pathlib
import sys

import httpx

from .phone import Phone

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "data" / "memory" / "second_run"


def picture(http) -> dict:
    """The parts of the app's own replies that show what a run starts with or ends with."""
    state = http.get("/api/state").json()
    titles = {c["id"]: c["product"] for line in state["lines"] for c in line["candidates"]}
    recalled = http.get("/api/memory/recall").json()
    return {
        "at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "sheet": state["sheet"]["id"], "mode": state["mode"], "sheet_hash": state["sheet_hash"],
        "receipt_chain": state["receipts"]["chain"], "receipts_verified": state["receipts"]["verified"],
        "signed": state["seal"]["signed"], "seal": state["seal"]["text"], "total_cents": state["total_cents"],
        "measurements": [{k: f.get(k) for k in ("id", "value", "unit", "remembered", "measured_by", "measured_at")}
                         for f in state["sheet"]["shopper_facts"]],
        "items": [{"line_id": line["line_id"], "need": line["need"],
                   "pick": (titles.get(line["pick"]) or {}).get("title"),
                   "pick_key": (titles.get(line["pick"]) or {}).get("product_key"),
                   "struck": line["struck"]} for line in state["lines"]],
        "applied_from_memory": state.get("memory"), "degraded": state["degraded"],
        "recalled": {"counts": recalled["counts"], "read_from": recalled["read_from"], "facts": recalled["facts"],
                     "strikes": recalled["strikes"], "purchases": recalled["purchases"],
                     "store_answers": [{k: a[k] for k in ("store", "key", "text", "asked_at", "age")}
                                       for a in recalled["store_answers"]]},
    }


def main(base="http://127.0.0.1:8007", reason="Suction mounts are not for a person's full weight."):
    http = httpx.Client(base_url=base, timeout=60)
    post = lambda path, body=None: http.post(path, json=body or {})  # noqa: E731
    assert post("/api/admin/reset").status_code == 200
    start = picture(http)
    phone = Phone(start["sheet"])
    code = http.get("/api/issuer/enroll-code").json()["code"]
    phone.key_id = post("/api/issuer/enroll", {"public_key_jwk": phone.jwk, "name": "Dana", "code": code}).json()["key_id"]

    fact = http.get("/api/state").json()["sheet"]["shopper_facts"][0]
    moved = fact["value"] + fact["step"]
    changed = post("/api/shopper/fact", {"fact_id": fact["id"], "value": moved})
    assert changed.status_code == 200, changed.text

    item = [i for i in picture(http)["items"] if i["pick_key"]][-1]
    struck = post("/api/issuer/request", phone.request("strike", line_id=item["line_id"], product_key=item["pick_key"], reason=reason))
    assert struck.status_code == 200, struck.text
    signed = post("/api/issuer/request", phone.request("sign_sheet", sheet_hash=http.get("/api/state").json()["sheet_hash"]))
    assert signed.status_code == 200, signed.text
    run1 = picture(http)

    assert post("/api/admin/reset").status_code == 200  # the reset forgets the key, the seal, the strikes, the measurements
    run2 = picture(http)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "run1.json").write_text(json.dumps(run1, indent=1, ensure_ascii=False) + "\n")
    (OUT / "run2.json").write_text(json.dumps(run2, indent=1, ensure_ascii=False) + "\n")

    after = {m["id"]: m for m in run2["measurements"]}[fact["id"]]
    line2 = next(i for i in run2["items"] if i["line_id"] == item["line_id"])
    again = [s for s in line2["struck"] if s.get("product_key") == item["pick_key"]]
    checks = {
        "run 2 is a new run (new chain, not signed, no key)": run2["receipt_chain"] != run1["receipt_chain"] and not run2["signed"],
        "the measurement is remembered": after["value"] == moved and after.get("remembered") is True,
        "with who and when": bool(after.get("measured_by")) and bool(after.get("measured_at")),
        "the struck product is out, from memory": bool(again) and again[0].get("from_memory") is True and line2["pick_key"] != item["pick_key"],
        "with the approver's reason": bool(again) and again[0].get("reason") == reason,
        "the stores' answers are reused with their age": bool(run2["recalled"]["store_answers"]) and all(
            a["age"]["seconds"] for a in run2["recalled"]["store_answers"]),
        "the signed order is remembered": len(run2["recalled"]["purchases"]) >= 1,
    }
    print("measurement  %s: %s -> %s %s; run 2 starts at %s (by %s, %s)" % (
        fact["id"], fact["value"], moved, fact["unit"], after["value"], after.get("measured_by"), after.get("measured_at")))
    print("struck       %s: %r; run 2 pick: %r" % (item["line_id"], item["pick"], line2["pick"]))
    print("struck again %s" % json.dumps(again, ensure_ascii=False))
    print("answers      %d reused, e.g. %s (%s old)" % (len(run2["recalled"]["store_answers"]),
          run2["recalled"]["store_answers"][0]["text"], run2["recalled"]["store_answers"][0]["age"]["text"]))
    print("recalled     %(recalled)d of %(of)d" % run2["recalled"]["counts"])
    for name, ok in checks.items():
        print("%s  %s" % ("ok  " if ok else "FAIL", name))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:2]))
