"""Writes evals/firedrill/_local/descriptor.json and plan.json for the Firedrill campaign.

    uv run python evals/firedrill/build_local.py descriptor
    uv run python evals/firedrill/build_local.py plan <descriptor digest printed by `firedrill register`> [path]

`path` is the chat endpoint: /chat (Sign-Off's agent, default) or /chat-plain (the plain agent, for the comparison).
_local/ holds absolute paths of this machine and stays out of git. Firedrill starts one fresh process per drill."""
import hashlib
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
LOCAL = pathlib.Path(__file__).resolve().parent / "_local"
AGENT_FILE = ROOT / "signoff" / "sign" / "firedrill_agent.py"
NODE = ("const c=require('crypto'),f=require('fs');const p=f.realpathSync(process.argv[1]);const s=f.statSync(p,{bigint:true});"
        "console.log(c.createHash('sha256').update('firedrill.root-identity.v1\\0').update(p).update('\\0')"
        ".update(`${s.dev}:${s.ino}`).digest('hex'))")


def root_identity():
    return subprocess.check_output(["node", "-e", NODE, str(ROOT)], text=True).strip()


def descriptor():
    return {
        "schema": "firedrill.local-descriptor.v1",
        "source_roots": [{"alias": "app", "identity_sha256": root_identity()}],
        "services": [{"alias": "agent", "root_alias": "app", "role": "agent", "depends_on": [], "configuration": []}],
        "entry_service": "agent",
        "driver": {"profile": "http.v1", "adapter_sha256": hashlib.sha256(AGENT_FILE.read_bytes()).hexdigest(),
                   "authentication": "anonymous", "state_domains": ["proc"]},
        "state_domains": [{"alias": "proc", "service_alias": "agent", "kind": "process", "location": "local",
                           "reset": "fresh-process", "concurrency": "independent", "hook_sha256": None}],
        "dependencies": [],
    }


def plan(digest, path="/chat"):
    return {
        "version": 1, "descriptor_sha256": digest,
        "roots": [{"alias": "app", "path": str(ROOT), "identity_sha256": root_identity()}],
        "services": [{
            "alias": "agent", "root_alias": "app", "mode": "launch",
            "command": {"executable": str(ROOT / ".venv" / "bin" / "python"), "args": ["-m", "signoff.sign.firedrill_agent"]},
            "cwd": ".", "env_passthrough": ["HOME", "PATH"], "env_static": {"SIGNOFF_SHEET": os.environ.get("FIREDRILL_SHEET", "sheet4")}, "local_secret_env": [],
            "readiness": {"kind": "http", "url": "http://127.0.0.1:0/health", "expect_status": [200]},
            "readiness_timeout_ms": 90000, "stop_timeout_ms": 5000, "per_drill": True, "port_env": "PORT"}],
        "driver": {"profile": "http.v1", "service_alias": "agent", "path": path, "method": "POST", "stream": "none",
                   "session_header": None, "request_template": "message-text", "response_pointer": "/reply"},
        "state_hooks": [], "max_parallel_drills": 1}


if __name__ == "__main__":
    LOCAL.mkdir(exist_ok=True)
    if sys.argv[1] == "descriptor":
        (LOCAL / "descriptor.json").write_text(json.dumps(descriptor(), indent=1))
    else:
        (LOCAL / ("plan%s.json" % ("" if len(sys.argv) < 4 or sys.argv[3] == "/chat" else "-plain"))).write_text(
            json.dumps(plan(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "/chat"), indent=1))
