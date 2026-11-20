"""The phone shows the same short grouped code as the laptop, and no internal id (reviews of 15:08)."""
import json
import re
import subprocess

from signoff.sign import senso

from .sheet4_state import build
from .standin import ROOT

HTML = (ROOT / "web" / "phone" / "index.html").read_text()


def node(expr):
    fn = HTML.split("/* the fingerprint as the laptop")[1].split("/* ---------- boot")[0]
    fn = fn.split("*/", 1)[1]
    out = subprocess.run(["node", "-e", "const esc=(s)=>String(s??'');" + fn + "\nconsole.log(JSON.stringify(%s))" % expr], capture_output=True, text=True, timeout=20)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_the_code_is_the_laptops_short_grouped_form():
    full = "3ac94ba1dd017b630f41a98f948eecca6496afb15c8a580af0819cf3ea172324"
    assert node('shortCode("%s")' % full) == "3ac9 4ba1 dd01"          # the same as web/seal/seal.js `short`
    block = node('codeBlock("%s")' % full)
    assert block.startswith('<div class="code">3ac9 4ba1 dd01</div>') and full in block and "<details>" in block   # the whole value is behind a tap
    seal_js = (ROOT / "web" / "seal" / "seal.js").read_text()
    assert 'slice(0, 12).replace(/(.{4})(?=.)/g, "$1 ")' in seal_js and 'slice(0, 12).replace(/(.{4})(?=.)/g, "$1 ")' in HTML


def test_no_internal_id_is_printed_on_the_phone():
    visible = re.sub(r"<style>.*?</style>", "", HTML, flags=re.S)
    assert not re.search(r"esc\([^)]*(inquiry_id|\bseq\b|currency|\.mode)", visible), re.search(r"esc\([^)]*(inquiry_id|\bseq\b|currency|\.mode)", visible).group(0)
    assert "· replay" not in visible and "USD" not in visible


def test_the_order_sentence_for_a_line_is_not_keyed_to_one_product(monkeypatch):
    assert not hasattr(senso, "ORDER_NAME")
    monkeypatch.setattr(senso, "_order_text", lambda sheet: "")       # an order document that does not line up: the sheet's own words
    rows = senso.sentences_for(build())
    assert any("shower chair" in r["sentence"] and "transfer bench" not in r["sentence"] for r in rows if r["kind"] == "order")
