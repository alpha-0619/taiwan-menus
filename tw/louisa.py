"""路易莎咖啡 LOUISA COFFEE: read the official product pages into a record (no AI step).

The menu is one page per category on https://www.louisacoffee.co/products_list/<id>. After the line '總共有 N 項產品'
each item is: Chinese name, sometimes 'New', usually an English name, then its price lines, then the page's own
note for that item (<span class="Note-Text">: 蛋奶素, (無咖啡因), 僅供內用熱飲 ...). Sub-headings are
<h5 class="uppercase"> (早餐派對, 英國百年茶莊系列 ...). Both are marked before the text is taken so they cannot be
mistaken for items. Price lines: 'M $90' / 'L $110' (drinks), '$75' (food), '$80/單片' (pastries), '$ $50',
'$85/單片 (限定門市販售)', and the page's own typo '$$65/單個'. Page notes start with '．' or name where the meat is from.
Left out on purpose: 濾掛／浸泡咖啡系列 (boxed retail coffee), 會議型糕點 (catering, no prices), 商品 (merchandise).
Checked 2026-10-23 in a browser: 燕麥拿鐵(冰) M $90 / L $110 on 經典義式咖啡.
"""
import re

from tw.text import page_text

SLUG = "louisa"
NAME = "路易莎咖啡"
URL = "https://www.louisacoffee.co/products"
CATEGORIES = [(8, "經典義式咖啡"), (10, "精品咖啡"), (11, "嚴選在地小農牧場系列"), (12, "茶與其他飲品"),
              (17, "享瘦低醣新食感"), (13, "輕食"), (14, "軟歐藏心貝果"), (6, "糕點"), (20, "La Merenda食光點心")]
URLS = [f"https://www.louisacoffee.co/products_list/{cid}" for cid, _ in CATEGORIES]
LIST = "價格"
NOTE, SUB = "＃備註：", "＃小標："

CJK = re.compile(r"[一-鿿]")
SIZE = re.compile(r"^[ML]$")
DOLLAR = re.compile(r"^\$$")
# 'M $90', '$ $50', '$$65/單個', '$80/單片', '$35 / 原味', '$75', '$85/單片 (限定門市販售)'
PRICE = re.compile(r"^(?:([ML])\s+)?(?:\$\s+)?\$+\s?(\d{2,4})(?:\s*/\s*([^\s(（]+))?\s*(?:[（(]([^)）]*)[)）])?$")
VARIANT = re.compile(r"^\$([^\d$\s][^\d]*[一-鿿][^\d]*)$")  # '$培根蔬食／三杯杏鮑菇': flavours above the price
ORIGIN = re.compile(r"產地[:：]")


def _sub_heading(m):
    """<h5 class="uppercase"> holds a sub-heading (<strong>早餐派對</strong> + English), or only a picture."""
    inner = m.group(1)
    strong = re.search(rb"<strong[^>]*>(.*?)</strong>", inner, re.S)
    zh = page_text(strong.group(1) if strong else b"").replace("\n", " ").strip()
    return ("<br>" + SUB + zh + "<br>").encode()


def marked_text(raw):
    raw = re.sub(rb"(?s)<!--.*?-->", b" ", raw)
    raw = re.sub(rb'<span class="Note-Text"[^>]*>', ("<br>" + NOTE).encode(), raw)
    raw = re.sub(rb'(?s)<h5 class="uppercase[^"]*"[^>]*>(.*?)</h5>', _sub_heading, raw)
    return page_text(raw)


def is_english(line):
    return (not CJK.search(line) and re.search(r"[A-Za-z]", line) and not SIZE.match(line)
            and not PRICE.match(line) and line != "New" and not line.startswith(("＃", "．")))


def is_price_token(line):
    return bool(SIZE.match(line) or DOLLAR.match(line) or PRICE.match(line))


def body_lines(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    start = next((i for i, l in enumerate(lines) if l.startswith("總共有") and l.endswith("項產品")), None)
    if start is None:
        raise ValueError("no '總共有 N 項產品' line: the page did not load or changed shape")
    end = next((i for i in range(start + 1, len(lines)) if lines[i] == "熱門訊息" or lines[i].startswith("©")), len(lines))
    return lines[start + 1:end]


def parse_page(text, category, url):
    """One category page's text -> (sections, page notes, names printed without a price)."""
    body = body_lines(text)
    sections, notes, unpriced, sub, last, i = [], [], [], None, None, 0
    while i < len(body):
        line = body[i]
        if line.startswith(NOTE):
            note = line[len(NOTE):].strip()
            if last is not None and note:
                last["note"] = "；".join(x for x in (last["note"], note) if x)
            i += 1
            continue
        if line.startswith(SUB):
            sub = line[len(SUB):].strip() or None
            i += 1
            continue
        if line.startswith("．") or ORIGIN.search(line):
            notes.append(line)
            i += 1
            continue
        if not CJK.search(line):
            i += 1
            continue
        j, en, variant = i + 1, "", ""
        if j < len(body) and body[j] == "New":
            j += 1
        if j < len(body) and is_english(body[j]):
            en, j = body[j], j + 1
        head = j
        if j < len(body) and VARIANT.match(body[j]):
            variant, j = VARIANT.match(body[j]).group(1).strip(), j + 1
        if j >= len(body) or not is_price_token(body[j]):
            unpriced.append(line)
            last = None
            i += 1
            continue
        prices, label, extra = {}, None, []
        while j < len(body) and is_price_token(body[j]):
            tok = body[j]
            if SIZE.match(tok):
                label = tok
            elif PRICE.match(tok):
                m = PRICE.match(tok)
                key = m.group(1) or label or m.group(3) or "單價"
                if key in prices:
                    raise ValueError(f"{line}: two prices for '{key}' on {url}; the page may have changed shape")
                prices[key] = int(m.group(2))
                if m.group(4):
                    extra.append(m.group(4))
                label = None
            j += 1
        name = f"{category}．{sub}" if sub else category
        if not sections or sections[-1]["name"] != name:
            sections.append({"name": name, "source": url, "items": []})
        last = {"name_zh": line + (f"（{variant}）" if variant else ""), "name_printed": line, "name_en": en,
                "prices_by_list": {LIST: prices}, "printed": body[head:j], "note": "；".join(extra)}
        sections[-1]["items"].append(last)
        i = j
    return sections, notes, unpriced


def parse(raws):
    """{official url: page bytes} -> (record without dates, combined page text)."""
    sections, notes, texts, unpriced = [], [], [], []
    for (cid, category), url in zip(CATEGORIES, URLS):
        text = marked_text(raws[url])
        texts.append(f"=== {url}\n{text}")
        secs, page_notes, page_unpriced = parse_page(text, category, url)
        if not secs:
            raise ValueError(f"no priced items on {url}")
        sections += secs
        notes += [n for n in page_notes if n not in notes]
        unpriced += page_unpriced
    left_out = "沒收進本頁：濾掛／浸泡咖啡系列（盒裝咖啡）、會議型糕點、商品（周邊）"
    rec = {
        "slug": SLUG, "name_zh": NAME, "name_en": "LOUISA COFFEE", "currency": "TWD", "cuisine": "咖啡",
        "source_url": URL, "price_lists": [LIST], "areas": {},
        "sections": sections,
        "notes_official": notes,
        "notes_zh": left_out + ("；官網沒寫價錢：" + "、".join(unpriced) if unpriced else "") + "。M、L 是官網寫的杯型。",
    }
    return rec, "\n".join(texts)


def check(rec, text):
    """Every item's printed price lines must sit right under its name (after an optional New tag and English name)
    on the same official page."""
    pages = {}
    for block in text.split("=== ")[1:]:
        url, _, body = block.partition("\n")
        pages[url.strip()] = [l.strip() for l in body.splitlines() if l.strip()]
    bad = []
    for s in rec["sections"]:
        lines = pages.get(s["source"], [])
        for it in s["items"]:
            ok = False
            for i in (k for k, l in enumerate(lines) if l == it["name_printed"]):
                j = i + 1
                if j < len(lines) and lines[j] == "New":
                    j += 1
                if it["name_en"] and j < len(lines) and lines[j] == it["name_en"]:
                    j += 1
                if lines[j:j + len(it["printed"])] == it["printed"]:
                    ok = True
                    break
            if not ok:
                bad.append(f"{s['name']} {it['name_zh']}")
    return bad
