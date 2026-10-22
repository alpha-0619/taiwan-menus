"""可不可熟成茶行: read the official menu page into a record (no AI step).

Each item on https://kebuke.com/menu/ is: name, then one price line per price list in the page's tab order
(北部及離島, 其他地區, 商場特規店), then a description and the nutrition lines (【中杯】/【大杯】 糖量、熱量、咖啡因).
Checked 2026-10-22 against the page's own tabs: 熟成紅茶 35/40, 30/35, 50 and 白玉奶茶 50/60, 50/60, 70 sit on those tabs.
"""
import re

from tw.text import page_text

SLUG = "kebuke"
URL = "https://kebuke.com/menu/"
NAME = "可不可熟成茶行"
REGIONS = ["北部及離島", "其他地區", "商場特規店"]
AREAS = {"北部及離島": "新北、台北、基隆、桃園、新竹與離島",
         "其他地區": "宜蘭、花蓮、台東、苗栗、台中、彰化、南投、雲林、嘉義、台南、高雄、屏東",
         "商場特規店": "百貨商場內的門市（多數品項只列大杯）"}
SIZED = re.compile(r"^(?:[中大]：\s?\d{2,3})(?:\s*/\s*[中大]：\s?\d{2,3})?$")
BARE = re.compile(r"^\d{2,3}$")
SECTION = re.compile(r"^(季節限定|乎乾 .+|金蒔燒 .+)$")
LEFT_OUT = re.compile(r"^金蒔燒")  # two named stores only; four unlabeled prices: which price is which list is not printed


def sized(line):
    return {k: int(v) for k, v in re.findall(r"([中大])：\s?(\d{2,3})", line)}


def parse(raw):
    """Official page bytes -> (record without dates, page text)."""
    text = page_text(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    start = lines.index("季節限定")
    end = next(i for i, l in enumerate(lines) if l.startswith("【＋$"))
    body, notes = lines[start:end], lines[end:]
    sections, cur, i = [], None, 0
    while i < len(body):
        line = body[i]
        if SECTION.match(line):
            cur = {"name": line, "items": []}
            sections.append(cur)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if cur is not None and (SIZED.match(nxt) or BARE.match(nxt)):
            j, prices = i + 1, []
            while j < len(body) and (SIZED.match(body[j]) or BARE.match(body[j])):
                prices.append(body[j])
                j += 1
            desc = body[j] if j < len(body) and not body[j].startswith(("【", "#", "糖量", "●")) else ""
            nutr, k = [], j + (1 if desc else 0)
            while k < len(body) and (body[k].startswith(("【中杯】", "【大杯】", "糖量", "咖啡因", "#", "●"))
                                     or "kcal" in body[k].lower()):
                nutr.append(body[k])
                k += 1
            if BARE.match(prices[0]):
                by_list = {REGIONS[n]: {"單價": int(p)} for n, p in enumerate(prices[:3])}
            else:
                by_list = {REGIONS[n]: sized(p) for n, p in enumerate(prices[:3])}
            cur["items"].append({"name_zh": line, "prices_by_list": by_list, "printed": prices[:3], "desc": desc,
                                 "nutrition": [x for x in nutr if not x.startswith(("#", "●"))]})
            i = k
            continue
        i += 1
    left_out = [s["name"] for s in sections if LEFT_OUT.match(s["name"])]
    sections = [s for s in sections if not LEFT_OUT.match(s["name"])]
    rec = {
        "slug": SLUG, "name_zh": NAME, "name_en": "KEBUKE Tea Co.", "currency": "TWD", "cuisine": "手搖飲",
        "source_url": URL, "price_lists": REGIONS, "areas": AREAS,
        "sections": sections,
        "notes_official": [n for n in notes if n.startswith(("•", "【北部", "【其他", "【＋$", "糖液", "雪花", "咖啡因", "原料"))],
        "notes_zh": ("沒收進本頁：" + "、".join(left_out) + "。官網寫只在兩家門市賣，而且列了四個價錢、沒寫各是哪一種價目。")
        if left_out else "",
    }
    return rec, text


def check(rec, text):
    """Every item's printed price lines must sit right under its name in the official text, in list order."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bad = []
    for s in rec["sections"]:
        for it in s["items"]:
            spots = [i for i, l in enumerate(lines) if l == it["name_zh"]]
            if not any(lines[i + 1:i + 1 + len(it["printed"])] == it["printed"] for i in spots):
                bad.append(it["name_zh"])
    return bad
