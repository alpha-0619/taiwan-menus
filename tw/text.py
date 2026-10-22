"""Plain text of a web page (same rules as the Menu Check harvester)."""
import html
import re


def page_text(raw):
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr|td|section|article)>", "\n", s)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    lines = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in s.splitlines()]
    return "\n".join(l for l in lines if l)
