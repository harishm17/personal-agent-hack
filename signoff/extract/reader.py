"""The model's half of reading a figure: it proposes figure, kind, numbers, unit and the exact quote.

It is never asked for offsets and never asked whether a product is suitable. `spans.finish` turns a
proposal into a record, and only code decides whether the quote is in the store's text.

Model routing (env `SIGNOFF_READER_MODEL`): `sie:<model>` is a generative model on Superlinked SIE
Serverless; `claude...` is Anthropic (the `claude -p` command line until `ANTHROPIC_API_KEY` exists);
`arcee:<model>` or any other id is Arcee. SIE and Arcee are both OpenAI-compatible chat endpoints.
"""
import json
import os
import logging
import pathlib
import subprocess
import tempfile
import time

import httpx

from signoff import config
from signoff.engine import health, obs

DEFAULT_MODEL = "claude-sonnet-5-5"  # the reference reader (CONTRACT.md, amendment 11:25)
ARCEE_URL = "https://api.arcee.ai/api/v1/chat/completions"
SIE_URL = "https://api.superlinked.com/v1/chat/completions"

SYSTEM = """You read the text of one product page from an online store and report what it states about some figures.
You report what is written; code decides what counts. You never fill a gap and never judge the product.

You are given the figures to look for, each with what it means. For each figure, return one entry for every
place the text states it. A page may state a figure once, several times, with different numbers, or not at
all: return every statement you find, and nothing for a figure the text does not state. Each entry:
- "figure": the figure's name as given.
- "quote": the words of the text that state it, copied character for character (same spelling, punctuation,
  spacing and symbols). One short contiguous passage that contains the number or numbers and the words that
  say what they measure. Code searches for the quote in the text; a quote that is not found is thrown away.
- "kind": "single" for one number. "adjustable" when the text gives a range the user can set the product to:
  give "low" and "high". "spread" when the text gives one size loosely as a range, or gives several values
  together for the one figure: give "low" and "high". For "single" give "value".
- "unit": the unit as the text writes it beside the number, or null when the text gives the number without
  a unit. Report the number as written; do not convert.
- "label": the word or words the text itself puts on the number you report, copied from the quote (the name
  written beside the number, or its heading in a list of headings); null when the quote has none.
- "note": null, or a few words when something about this statement should be known: the option, size or
  model it is given for, or what else on the page speaks against it.
The text may end with "Selected option: ...": that is the option this page is for. When the text gives the
figure per option, report the statement for that option, and say so in "note".

Answer with one JSON object and nothing else:
{"figures": [{"figure": "<name>", "quote": "...", "kind": "single", "value": 7.25, "low": null, "high": null,
"unit": "<unit as written>", "label": "...", "note": null}]}"""


# The instructions as they were when the committed readings were made: identical except for the example at the
# end, which showed `"value": 300 ... "unit": "lb"`. An example must not be any sheet's figure or bound, so it now
# shows a value and a unit no sheet uses. A sample re-read under the new example is reported in the notes.
SYSTEM_WITH_THE_OLD_EXAMPLE = SYSTEM.replace('"value": 7.25,', '"value": 300,').replace('"unit": "<unit as written>"', '"unit": "lb"')
assert SYSTEM_WITH_THE_OLD_EXAMPLE != SYSTEM


class NoMeaning(ValueError):
    """The sheet names a figure without saying what it means. The reader is not given a bare word to guess from."""


def meanings(names, sheet):
    """What each figure means, in the sheet's own words (`figures` in the sheet file). No built-in list."""
    given = sheet.get("figures") or {}
    missing = [n for n in names if not given.get(n)]
    if missing:
        raise NoMeaning("sheets/%s.json gives no meaning for %s under \"figures\"" % (sheet.get("id"), ", ".join(missing)))
    return {n: given[n] for n in names}


def wanted_figures(product, sheet):
    """The store figures the limits of this product's lines are summed from."""
    names = []
    for line in sheet["lines"]:
        if line["id"] in product.get("line_ids", []):
            for limit in line["limits"]:
                for term in limit["terms"]:
                    if term["source"] == "store" and term["figure"] not in names:
                        names.append(term["figure"])
    return names


def figure_units(sheet):
    """{figure name: the unit of the limit it is summed into}, from the sheet."""
    out = {}
    for line in sheet["lines"]:
        for limit in line["limits"]:
            for term in limit["terms"]:
                if term["source"] == "store":
                    out.setdefault(term["figure"], limit["unit"])
    return out


def prompt_for(product, names, sheet):
    """The user message of a figure read: the figures with their meanings and units, and the page's text.
    Nothing else: no limit, no measurement of the home, no person."""
    given, units = meanings(names, sheet), figure_units(sheet)
    asked = "\n".join("- %s (%s): %s" % (n, units.get(n, "a number"), given[n]) for n in names)
    return "Figures to report:\n%s\n\nProduct page text, between the markers:\n<<<TEXT\n%s\nTEXT>>>" % (
        asked, product.get("text") or "")


def parse(reply):
    """The JSON object in a model reply, tolerant of code fences and words around it."""
    if not reply:
        raise ValueError("empty reply")
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the reply")
    obj = json.loads(reply[start:end + 1])
    figures = obj.get("figures")
    if not isinstance(figures, list):
        raise ValueError("no figures list in the reply")
    return [f for f in figures if isinstance(f, dict)]


def ask_openai_style(url, key, model, system, user, timeout=120.0, max_tokens=2000, tries=6):
    """One chat completion. A cold SIE model answers 503 with Retry-After: wait and ask again."""
    for attempt in range(tries):
        response = httpx.post(url, timeout=timeout, headers={"Authorization": "Bearer %s" % key},
                              json={"model": model, "temperature": 0, "max_tokens": max_tokens,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]})
        if response.status_code in (429, 503) and attempt < tries - 1:
            time.sleep(min(float(response.headers.get("retry-after") or 2 * (attempt + 1)), 30.0))
            continue
        response.raise_for_status()
        body = response.json()
        return body["choices"][0]["message"].get("content") or "", body.get("usage") or {}


_CLI_CWD = pathlib.Path(tempfile.gettempdir()) / "signoff-reader-cwd"


def _cli_env():
    """The command line must run on its own login. The keys file puts ANTHROPIC_API_KEY into this process's
    environment; passed on, the command line would bill every batch read to that key instead."""
    return {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")}


def ask_claude_cli(model, system, user, timeout=180.0):
    """`claude -p` with no tools, no project settings and no session file, run outside the repo."""
    _CLI_CWD.mkdir(exist_ok=True)
    done = subprocess.run(
        ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "", "--strict-mcp-config",
         "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
         "--system-prompt", system],
        input=user, capture_output=True, text=True, timeout=timeout, cwd=_CLI_CWD, env=_cli_env())
    if done.returncode != 0:
        raise RuntimeError("claude -p failed: %s" % (done.stderr or done.stdout)[:300])
    body = json.loads(done.stdout)
    if body.get("is_error"):
        raise RuntimeError("claude -p error: %s" % str(body.get("result"))[:300])
    return body.get("result") or "", dict(body.get("usage") or {}, cost_usd=body.get("total_cost_usd"))


API_CALL_CAP = 60  # per process: the API key has little credit; batch reads never use it
_api_calls = {"made": 0, "capped_logged": False}
log = logging.getLogger("signoff.reader")


def ask_anthropic_api(model, system, user, max_tokens=4000):
    """One Messages API call through the Anthropic SDK: no retries, no sampling parameters (current models
    reject them), low effort because the task is short. A policy decline is re-run by the server on its
    default fallback model; if it still declines, raise."""
    import anthropic
    _api_calls["made"] += 1
    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"), timeout=12.0, max_retries=0)
    response = client.beta.messages.create(
        model=model, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
        output_config={"effort": "low"}, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    if response.stop_reason == "refusal":
        raise RuntimeError("the model declined this request")
    text = "".join(block.text for block in response.content if block.type == "text")
    usage = {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens,
             "via": "api", "served_by": response.model}
    return text, usage


def ask_anthropic(model, system, user, live=False):
    """`claude -p`, always, for batch work. Only a live call (one a person is waiting on) may use the API
    key, at most API_CALL_CAP times per process and never retried; any API failure falls back to `claude -p`."""
    if live and config.have("ANTHROPIC_API_KEY") and config.env("SIGNOFF_ANTHROPIC_VIA") != "cli":
        if _api_calls["made"] >= API_CALL_CAP:
            if not _api_calls["capped_logged"]:
                _api_calls["capped_logged"] = True
                log.warning("Anthropic API call cap reached (%d calls in this process): using claude -p from now on",
                            API_CALL_CAP)
                health.note("live model", "the cap of %d API-key calls in this process is reached; live calls now go "
                            "through the command line, which is slower" % API_CALL_CAP)
        else:
            try:
                made = ask_anthropic_api(model, system, user)
                health.clear("live model")
                return made
            except Exception as error:  # noqa: BLE001  (bad key, no credit, a rejected parameter, the network)
                log.warning("Anthropic API call failed (%s): using claude -p for this one", type(error).__name__)
                health.note("live model", "the last API-key call failed (%s); it was answered through the command "
                            "line instead" % type(error).__name__)
    return ask_claude_cli(model, system, user, timeout=25.0 if live else 180.0)  # a person is waiting: fail soon


def recipient_of(model):
    if model.startswith("claude"):
        return "anthropic:%s" % model
    return model if model.startswith("sie:") else "arcee:%s" % model.replace("arcee:", "")


def ask(model, system, user, live=False, purpose="read figures from one store page",
        fact_classes=("store_text", "product")):
    """(reply text, usage, extractor name). `live=True` only for a call a person is waiting on.
    Every call is entered in the outbound ledger first: recipient, purpose, the two strings sent, and the
    kinds of fact they hold. A figure read holds the store's text and the figure names, nothing else."""
    obs.egress(recipient_of(model), purpose, {"system": system, "user": user}, fact_classes)
    if model.startswith("claude"):
        text, usage = ask_anthropic(model, system, user, live)
        return text, usage, "anthropic:%s" % model
    if model.startswith("sie:"):
        text, usage = ask_openai_style(SIE_URL, config.env("SIE_API_KEY"), model[4:], system, user)
        return text, usage, model
    name = model[6:] if model.startswith("arcee:") else model
    text, usage = ask_openai_style(ARCEE_URL, config.env("ARCEE_API_KEY"), name, system, user)
    return text, usage, "arcee:%s" % name


def read(product, sheet, model=None, tries=2):
    """Proposals for one product: (list of stated proposals, extractor name, usage, asked figure names)."""
    model = model or config.env("SIGNOFF_READER_MODEL") or DEFAULT_MODEL
    names = wanted_figures(product, sheet)
    if not names:
        return [], "none", {}, names
    user, error = prompt_for(product, names, sheet), None  # raises NoMeaning when the sheet does not say what a figure is
    for _ in range(tries):
        try:
            reply, usage, extractor = ask(model, SYSTEM, user)
            proposals = [p for p in parse(reply) if p.get("stated", True) and p.get("figure") in names and p.get("quote")]
            return proposals, extractor, usage, names
        except Exception as e:  # noqa: BLE001  (a bad reply or a network error: try once more, then report)
            error = e
    raise RuntimeError("reader failed for %s %s: %r" % (product["store"], product["product_id"], error))
