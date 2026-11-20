"""The model's half of reading a figure: it proposes figure, kind, numbers, unit and the exact quote.

It is never asked for offsets and never asked whether a product is suitable. `spans.finish` turns a
proposal into a record, and only code decides whether the quote is in the store's text.

Model routing (env `SIGNOFF_READER_MODEL`): an id starting with `claude` goes to Anthropic (the `claude -p`
command line until `ANTHROPIC_API_KEY` exists); any other id goes to Arcee's OpenAI-compatible endpoint.
"""
import json
import pathlib
import subprocess
import tempfile

import httpx

from signoff import config

DEFAULT_MODEL = "zai-org/glm-5.3"
ARCEE_URL = "https://api.arcee.ai/api/v1/chat/completions"

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
    "length": "The length of the product itself (for a bar or rail, end to end).",
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


def prompt_for(product, names, sheet):
    meanings = dict(GLOSSARY, **(sheet.get("figures") or {}))
    asked = "\n".join("- %s: %s" % (n, meanings.get(n, n.replace("_", " "))) for n in names)
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


def ask_arcee(model, system, user, timeout=120.0, max_tokens=4000):
    response = httpx.post(ARCEE_URL, timeout=timeout,
                          headers={"Authorization": "Bearer %s" % config.env("ARCEE_API_KEY")},
                          json={"model": model, "temperature": 0, "max_tokens": max_tokens,
                                "messages": [{"role": "system", "content": system},
                                             {"role": "user", "content": user}]})
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
    return body.get("result") or "", body.get("usage") or {}


def ask(model, system, user):
    """(reply text, usage, extractor name)."""
    if model.startswith("claude"):
        text, usage = ask_claude_cli(model, system, user)
        return text, usage, "anthropic:%s" % model
    text, usage = ask_arcee(model, system, user)
    return text, usage, "arcee:%s" % model


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
