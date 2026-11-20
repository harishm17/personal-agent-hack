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


def phrases(label: str) -> list[list[str]]:
    parts = re.split(r"\s*(?:&|,|\||;|\s-\s|\s–\s|\swith\s|\sby\s|\sin\s|\sfor\s|\sand\s)\s*", html.unescape(label or ""), flags=re.I)
    out = []
    for p in parts:
        w = words(p)
        while w and w[-1].isdigit():  # a trailing size or count ("5-1/2") is not the thing's name
            w.pop()
        if w:
            out.append(w)
    return out


def need_parts(need: str) -> tuple[str, set[str]]:
    w = words(need)
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


def head_in(label: str, head: str) -> bool:
    """Does one of the label's phrases end with the head word of the need?"""
    return any(ph[-1] == head for ph in phrases(label))


def belongs(prod: dict, need: str) -> tuple[bool, str]:
    """(kept, why). The product's own title or one of the store's labels (collections, tags, text categories) has a phrase that
    ends with the head word of the need ("toilet", "seat", "rail": what the thing is), and, when the need has more words, the
    rest of the need is named somewhere in the title or the labels (what kind). `why` is recorded for kept and dropped alike."""
    head, rest = need_parts(need)
    labels = store_labels(prod)
    title = prod.get("title", "")
    sources = [("title", title)] + [("label", l) for l in labels]
    found = next((src for src in sources if head_in(src[1], head)), None)
    if not found:
        return False, "no phrase of its title or its %d store labels ends with %r" % (len(labels), head)
    named = set(words(" ".join([title] + labels)))
    if rest and not (rest & named):
        return False, "its %s %r ends with %r, but nothing in its title or labels names %s" % (
            found[0], found[1], head, " or ".join(sorted(rest)))
    return True, "its %s %r ends with %r%s" % (found[0], found[1], head, (" and it names " + ", ".join(sorted(rest & named))) if rest else "")
