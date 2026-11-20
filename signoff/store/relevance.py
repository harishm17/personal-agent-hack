"""One rule for whether a product belongs to a line, from the store's own data: no word list, no brand, no product type.

The store labels each product itself: the titles of the collections it sits in, its tags, its taxonomy category when it is
text, and its own title. A product belongs to a line when one of those labels, split into phrases at "&", "," "|", " - ",
" with " and " by ", has a phrase whose last word is the line's head word (the last word of `need`, singular) and, when
the need has more than one word, also holds another word of the need. "Raised Toilet Seats" matches "raised toilet seat" and
"Smart Toilets" matches "toilet"; "Toilet Paper Holders" does not match "toilet" (its head is "holders").
Collections, tags and categories are the store's own taxonomy and are asked first; the title is used only when the store
gave none of them. A product that matches nothing is dropped, and the reason is recorded.
"""
import html
import re


def stem(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if re.search(r"(ch|sh|x|ss|z)es$", w):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


def words(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[a-z0-9]+", html.unescape(text or "").lower())]


def _is_count(w: str) -> bool:
    """A size or count token: "24", "48pk", "12ct". It is a quantity, not the name of the thing."""
    return bool(re.fullmatch(r"\d+[a-z]{0,3}", w))


def phrases(label: str) -> list[list[str]]:
    parts = re.split(r"\s*(?:&|,|\||;|\s-\s|\s–\s|\swith\s|\sby\s|\sin\s|\sfor\s|\sand\s)\s*", html.unescape(label or ""), flags=re.I)
    out = []
    for p in parts:
        w = words(p)
        while w:  # a trailing size or count ("5-1/2", "48pk", "7 pack", "set of 4") is not the thing's name
            if _is_count(w[-1]) or w[-1] == "of":
                w.pop()
            else:
                break
        if w:
            out.append(w)
    return out


def need_parts(need: str) -> tuple[str, set[str]]:
    w = words(need)
    while w and _is_count(w[-1]):  # "crayons 24" names crayons; 24 is the quantity wanted
        w.pop()
    return (w[-1], set(w[:-1])) if w else ("", set())


def store_labels(prod: dict) -> list[str]:
    """The store's own taxonomy for the product: collection titles, tags, text categories."""
    out = [c.get("title") for c in prod.get("collections", []) if isinstance(c, dict) and c.get("title")]
    out += [t for t in prod.get("tags", []) if isinstance(t, str)]
    for c in prod.get("categories", []) or []:
        v = c.get("value") if isinstance(c, dict) else None
        if v and not str(v).startswith("gid://"):  # an id such as gid://shopify/TaxonomyCategory/... is not a name
            out.append(str(v))
    return out


def ends_with(ph: list[str], head: str) -> bool:
    """Does the phrase end with the head word, allowing a quantity after it ("Pencils 12 Pack": a number and a word)?"""
    return ph[-1] == head or (len(ph) >= 3 and ph[-2].isdigit() and ph[-3] == head)


def core(ph: list[str]) -> list[str]:
    """The phrase without a trailing quantity ("Commode Liner 7 Pack" -> "Commode Liner"): a number and the word after it."""
    return ph[:-2] if len(ph) >= 3 and ph[-2].isdigit() else ph


def head_in(label: str, head: str) -> bool:
    """Does one of the label's phrases end with the head word of the need?"""
    return any(ends_with(ph, head) for ph in phrases(label))


_FOR = re.compile(r"\b(?:for|fits?|compatible with)\b", re.I)


def belongs(prod: dict, need: str) -> tuple[bool, str]:
    """(kept, why). The product's own title or one of the store's labels (collections, tags, text categories) has a phrase that
    ends with the head word of the need ("toilet", "seat", "rail": what the thing is), and, when the need has more words, the
    rest of the need is named somewhere in the title or the labels (what kind). Two things in the title overrule the labels:
      - a title that says it is *for* the thing ("Replacement Leg Tips for Carex Shower Chair") is a part or an accessory: the
        thing named after "for" is not what is sold;
      - a title whose own head word is a different thing that the store's labels also name as a thing of its own ("Commode
        Liner" under a label "... Commode Liners") is that other thing.
    `why` is recorded for kept and dropped alike."""
    head, rest = need_parts(need)
    labels = store_labels(prod)
    title = prod.get("title", "")
    m = _FOR.search(title)
    own = title[:m.start()] if m else title  # what the title says it is, before any "for ..."
    if m and not any(ends_with(ph, head) for ph in phrases(own)):
        return False, "its title says it is for a %s (%r), not a %s itself" % (need, title[m.start():][:60], need)
    sources = [("title", own)] + [("label", l) for l in labels]
    found = next((src for src in sources if head_in(src[1], head)), None)
    if not found:
        return False, "no phrase of its title or its %d store labels ends with %r" % (len(labels), head)
    first = core(phrases(own)[0]) if phrases(own) else []
    if first and first[-1] != head and not any(ends_with(ph, head) for ph in phrases(own)):
        if any(core(ph)[-1] == first[-1] and head in core(ph)[:-1] for l in labels for ph in phrases(l)):  # e.g. a label "Commode Liners"
            return False, "its title names a %s, which the store's own labels list as a kind of its own (a %s of the %s), not a %s" % (
                first[-1], first[-1], head, head)
    named = set(words(" ".join([title] + labels)))
    if rest and not (rest & named):
        return False, "its %s %r ends with %r, but nothing in its title or labels names %s" % (
            found[0], found[1], head, " or ".join(sorted(rest)))
    return True, "its %s %r ends with %r%s" % (found[0], found[1], head, (" and it names " + ", ".join(sorted(rest & named))) if rest else "")
