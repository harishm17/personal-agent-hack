"""The model's half of reading a figure: it proposes figure, kind, numbers, unit and the exact quote.

It is never asked for offsets and never asked whether a product is suitable. `spans.finish` turns a
proposal into a record, and only code decides whether the quote is in the store's text.

Model routing (env `SIGNOFF_READER_MODEL`): `sie:<model>` is a generative model on Superlinked SIE
Serverless; `claude...` is Anthropic (the `claude -p` command line until `ANTHROPIC_API_KEY` exists);
`arcee:<model>` or any other id is Arcee. SIE and Arcee are both OpenAI-compatible chat endpoints.
"""
import json
import logging
import pathlib
import subprocess
import tempfile
import time

import httpx

from signoff import config
from signoff.engine import obs

DEFAULT_MODEL = "claude-sonnet-5-5"  # the reference reader (CONTRACT.md, amendment 11:25)
ARCEE_URL = "https://api.arcee.ai/api/v1/chat/completions"
SIE_URL = "https://api.superlinked.com/v1/chat/completions"

# What each figure name means. A sheet may carry its own under "figures": {name: definition}.
GLOSSARY = {
    "weight_capacity": "The heaviest person (or load) the product is rated to hold, e.g. 'supports up to 300 lbs'. "
                       "Not the product's own weight, not shipping weight.",
    "added_height": "How much height the product adds on top of what it sits on, e.g. a riser that 'adds 5 inches'. "
                    "Not the product's overall height and not the finished seat height.",
    "seat_height": "The height of the seat above the floor. Usually adjustable: report the range as 'adjustable'.",
    "overall_width": "The widest outside measurement of the whole product: 'overall width', the width in the overall "
                     "or product dimensions, or the width outside the legs or base. Seat width, the width between "
                     "the arms, inside width and depth are different measures: never report them as overall width.",
    "length": "The length of the product itself. When the page sells several sizes, report only the selected option's "
              "length (the text may end with 'Selected option: ...'). A size option named by its length (the 12\" bar "
              "among 'Available in 12\", 16\" and 18\" lengths', or 'Length: 12\" or 16\"') has that length: quote the "
              "passage that gives the lengths, which must contain the selected option's number, and do not mark it "
              "unsure for that reason alone. If the page gives the selected size both as a named size and as a longer "
              "installed or end-to-end measurement, report the named size. If the selected option's length is not "
              "given anywhere, it is not stated.",
    "mattress_thickness_max": "The thickest mattress the product fits. 'Fits mattresses 12 to 16 inches' is an "
                              "adjustable range.",
}

SYSTEM = """You read the text of one product page from an online store and report specific figures from it.
You only report what the text states. You do not judge the product and you never fill a gap.

For each figure asked for, return one entry:
- "stated": true only if the text states this exact measure for this product. A different measure does not
  count, however close (seat width is not overall width; the product's own weight is not its weight capacity).
  If it is not stated, return "stated": false and nulls. Not stated is a normal, useful answer.
- "quote": the words of the text that state it, copied character for character (same spelling, punctuation,
  spacing and symbols; do not tidy it). One short contiguous passage that contains the number or numbers and
  the words saying what they measure. Code will search for this quote in the text; a quote that is not
  found is thrown away.
- "kind": "single" for one number. "adjustable" when the user can set it anywhere in a range ("seat height
  adjusts from 16 to 21 inches"): give "low" and "high". "spread" when the product has one fixed size that the
  text gives loosely as a range ("adds 5 to 5.5 inches"): give "low" and "high". For "single" give "value".
- "unit": the unit as written, one of "lb", "kg", "in", "cm", "mm", "ft". If the text gives the number with
  no unit at all, use null. Report the number as written; do not convert.
- "unsure": true, with a short "unsure_reason", when the text gives different numbers for different sizes,
  models or options and it is not clear which applies to the selected option (the text may end with
  "Selected option: ..."), or when the passage is ambiguous in any other way. When the selected option does
  settle it, report that option's number and leave "unsure" false.

Answer with one JSON object and nothing else:
{"figures": [{"figure": "<name>", "stated": true, "kind": "single", "value": 300, "low": null, "high": null,
"unit": "lb", "quote": "...", "unsure": false, "unsure_reason": null}]}"""


# Raised when a figure's meaning above is reworded, so only the products asked for that figure are read again.
GLOSSARY_REVISION = {"length": 2}


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
    meanings = dict(GLOSSARY, **(sheet.get("figures") or {}))
    asked = "\n".join("- %s: %s" % (n, meanings.get(n, n.replace("_", " "))) for n in names)
    units = sorted({u for n, u in figure_units(sheet).items() if n in names and u not in ("lb", "in")})
    more = ("\nOn this sheet a unit may also be one of: %s (and the metric unit of the same kind). Report it as "
            "written.\n" % ", ".join(units)) if units else ""
    return "Figures to report:\n%s\n%s\nProduct page text, between the markers:\n<<<TEXT\n%s\nTEXT>>>" % (
        asked, more, product.get("text") or "")


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


def ask_claude_cli(model, system, user, timeout=180.0):
    """`claude -p` with no tools, no project settings and no session file, run outside the repo."""
    _CLI_CWD.mkdir(exist_ok=True)
    done = subprocess.run(
        ["claude", "-p", "--model", model, "--output-format", "json", "--tools", "", "--strict-mcp-config",
         "--setting-sources", "", "--disable-slash-commands", "--no-session-persistence",
         "--system-prompt", system],
        input=user, capture_output=True, text=True, timeout=timeout, cwd=_CLI_CWD)
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
        else:
            try:
                return ask_anthropic_api(model, system, user)
            except Exception as error:  # noqa: BLE001  (bad key, no credit, a rejected parameter, the network)
                log.warning("Anthropic API call failed (%s): using claude -p for this one", type(error).__name__)
    return ask_claude_cli(model, system, user, timeout=25.0 if live else 180.0)  # a person is waiting: fail soon


def recipient_of(model):
    if model.startswith("claude"):
        return "Anthropic (%s)" % model
    return "Superlinked SIE (%s)" % model[4:] if model.startswith("sie:") else "Arcee (%s)" % model


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
    user, error = prompt_for(product, names, sheet), None
    for _ in range(tries):
        try:
            reply, usage, extractor = ask(model, SYSTEM, user)
            proposals = [p for p in parse(reply) if p.get("stated") and p.get("figure") in names]
            return proposals, extractor, usage, names
        except Exception as e:  # noqa: BLE001  (a bad reply or a network error: try once more, then report)
            error = e
    raise RuntimeError("reader failed for %s %s: %r" % (product["store"], product["product_id"], error))
