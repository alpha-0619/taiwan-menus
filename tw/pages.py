"""Build docs/ (the published site) from data/*.json: one page per chain, the home page, sitemap.xml, llms.txt."""
import html
import json
import re
from pathlib import Path

SITE_URL = "https://alpha-0619.github.io/taiwan-menus"
GOAT = '<script data-goatcounter="https://menucheck.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
STYLE = """:root{--bg:#fff;--fg:#1c1c1c;--muted:#666;--line:#e3e3e3;--sec:#f4f1ea;--accent:#7a4b12}
@media (prefers-color-scheme:dark){:root{--bg:#151515;--fg:#eee;--muted:#aaa;--line:#333;--sec:#24211c;--accent:#e0b070}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Noto Sans TC","Microsoft JhengHei",sans-serif}
main{max-width:880px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;margin:.4em 0} .meta{color:var(--muted);font-size:.92rem}
a{color:var(--accent)} .wrap{overflow-x:auto;margin:1em 0}
table{border-collapse:collapse;width:100%;min-width:560px} th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}
thead th{font-size:.85rem;color:var(--muted)} tr.sec th{background:var(--sec);font-size:.95rem}
td:not(:first-child){white-space:nowrap}
tbody td:first-child,thead th:first-child{position:sticky;left:0;background:var(--bg);min-width:8.5em;z-index:1}
tr.sec th{position:sticky;left:0} ul{padding-left:1.2em} small{color:var(--muted)}"""


def esc(s):
    return html.escape(str(s or ""), quote=True)


def cell(p):
    """{'中': 35, '大': 40} -> '中 35 大 40'; {'單價': 50} -> '50'; {'單片': 80} -> '80／單片'; {'加價': 10} -> '+10'."""
    if not p:
        return "—"
    return " ".join(f"{v}" if k == "單價" else f"+{v}" if k == "加價" else f"{k} {v}" if k in ("小", "中", "大", "M", "L")
                    else f"{v}／{k}" for k, v in p.items())


def nutrition(lines):
    """('大杯', sugar, kcal) as printed; the 中杯 line when only a medium is sold."""
    for size in ("大杯", "中杯"):
        for i, line in enumerate(lines):
            if line.startswith(f"【{size}】") and i + 1 < len(lines):
                m = re.search(r"糖量：\s*([\d.]+)\s*g\s*；\s*熱量：\s*([\d.]+)\s*[Kk]cal", lines[i + 1])
                if m:
                    return size, m.group(1), m.group(2)
    return None


def head(title, desc, ld=None):
    return (f'<!doctype html>\n<html lang="zh-Hant-TW"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>{esc(title)}</title>\n'
            f'<meta name="description" content="{esc(desc)}">\n'
            + (f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n' if ld else "")
            + f"<style>{STYLE}</style></head><body><main>\n")


def is_shop(rec):
    """A restaurant's own menu, either sent to us (store_provided) or posted on its own page (store_posted):
    one date, no daily re-check."""
    return rec.get("kind") in ("store_provided", "store_posted")


def is_posted(rec):
    return rec.get("kind") == "store_posted"


def shop_dated(rec):
    """'店家 2026-10-25 提供' for a menu the shop sent us; '店家公布，2026-10-26 查證' for one it posted itself."""
    return f"店家公布，{rec['checked']} 查證" if is_posted(rec) else f"店家 {rec['checked']} 提供"


OTHER_NAMES = (("name_en", "en", "英"), ("name_ja", "ja", "日"), ("name_ko", "ko", "韓"))


def shop_page(rec):
    """The menu typed from what the restaurant sent, with the names it prints in other languages; no photo."""
    name, day = rec["name_zh"], rec["checked"]
    items = [it for s in rec["sections"] for it in s["items"]]
    langs = [zh for k, _, zh in OTHER_NAMES if any(it.get(k) for it in items)]
    if is_posted(rec):
        offer_note = f"店家公布的菜單價格（{day} 查證）"
        desc_src, title_src = f"照店家自己在粉專公布的菜單抄成文字，{day} 查證", f"店家公布，{day} 查證"
        foot = f"本頁照店家自己在粉專公布的菜單抄成文字，{day} 查證；只放文字，不放店家照片。"
    else:
        offer_note = f"店家 {day} 提供的菜單價格"
        desc_src, title_src = f"店家 {day} 傳來的菜單，抄成文字", f"店家 {day} 提供"
        foot = f"本頁照店家傳來的菜單抄成文字，寫的是店家 {day} 提供的價格；只放文字，不放店家照片。"
    rows, offers = [], []
    for s in rec["sections"]:
        rows.append(f'<tr class="sec"><th colspan="2">{esc(s["name"])}</th></tr>')
        for it in s["items"]:
            other = "".join(f'<br><small lang="{lang}">{esc(it[k])}</small>' for k, lang, _ in OTHER_NAMES if it.get(k))
            rows.append(f"<tr><td>{esc(it['name_zh'])}{other}</td><td>{esc(cell(it.get('prices')))}</td></tr>")
            for size, price in (it.get("prices") or {}).items():
                offers.append({"@type": "MenuItem", "name": it["name_zh"] if size == "單價" else f"{it['name_zh']}（{size}）",
                               "offers": {"@type": "Offer", "price": price, "priceCurrency": "TWD",
                                          "description": offer_note}})
    ld = {"@context": "https://schema.org", "@type": "Menu", "name": f"{name} 菜單", "inLanguage": "zh-TW",
          "url": f"{SITE_URL}/{rec['slug']}/", "hasMenuItem": offers}
    also = f"，附店家自己寫的{'、'.join(langs)}文菜名" if langs else ""
    city = rec["city"]
    desc = f"{city}{name}最新菜單價格（{len(items)} 品項）：{desc_src}{also}。"
    where = f"{esc(rec['address'])}．" if rec.get("address") else ""
    # Hours and phone as the shop's own Facebook page shows them, left out when it shows none we trust.
    info = "．".join(f"{label}：{esc(rec[k])}" for label, k in (("營業時間", "hours"), ("電話", "phone")) if rec.get(k))
    info = (f'<p class="meta">{info}（照店家臉書粉專，{rec["info_checked"]} 看；臨時公休或異動以店家公告為準）</p>\n'
            if info else "")
    return (head(f"{city}美食》{name}最新菜單價格 {day[:4]}（{title_src}）| Menu Check", desc, ld)
            + f'<p class="meta"><a href="../">Menu Check 台灣菜單</a></p>\n<h1>{esc(name)} 最新菜單價格</h1>\n'
            + f'<p class="meta">{where}{esc(rec["provided"])}．價格以店內為準</p>\n' + info
            + '<div class="wrap"><table style="min-width:0">\n<thead><tr><th>品項'
            + (f"（店家寫的{'、'.join(langs)}文）" if langs else "") + "</th><th>價格（新台幣）</th></tr></thead>\n<tbody>"
            + "".join(rows) + "</tbody></table></div>\n"
            + f"<p><small>{foot}</small></p>\n"
            + f"<p><small>Menu Check 不是{esc(name)}的官方網站，跟店家沒有合作關係。</small></p>\n"
            + f"</main>{GOAT}</body></html>\n")


def chain_page(rec):
    if is_shop(rec):
        return shop_page(rec)
    lists, name, day = rec["price_lists"], rec["name_zh"], rec["checked"]
    items = [it for s in rec["sections"] for it in s["items"]]
    has_nut = any(it.get("nutrition") for it in items)
    has_note = any(it.get("note") for it in items)
    cols = 1 + len(lists) + has_nut + has_note
    rows, offers = [], []
    for s in rec["sections"]:
        src = f' <small><a href="{esc(s["source"])}" rel="nofollow">官網這一頁</a></small>' if s.get("source") else ""
        rows.append(f'<tr class="sec"><th colspan="{cols}">{esc(s["name"])}{src}</th></tr>')
        for it in s["items"]:
            en = f'<br><small>{esc(it["name_en"])}</small>' if it.get("name_en") else ""
            row = ("<tr><td>" + esc(it["name_zh"]) + en + "</td>"
                   + "".join(f"<td>{esc(cell(it['prices_by_list'].get(l)))}</td>" for l in lists))
            if has_nut:
                nut = nutrition(it.get("nutrition", []))
                row += "<td>" + esc((f"{nut[2]} kcal / 糖 {nut[1]} g" + ("" if nut[0] == "大杯" else "（中杯）")) if nut else "—") + "</td>"
            if has_note:
                row += f"<td>{esc(it.get('note') or '')}</td>"
            rows.append(row + "</tr>")
            for size, price in (it["prices_by_list"].get(lists[0]) or {}).items():
                offers.append({"@type": "MenuItem", "name": it["name_zh"] if size == "單價" else f"{it['name_zh']}（{size}）",
                               "offers": {"@type": "Offer", "price": price, "priceCurrency": "TWD",
                                          "description": f"{lists[0]}價格" if len(lists) > 1 else "官網價格"}})
    ld = {"@context": "https://schema.org", "@type": "Menu", "name": f"{name} 菜單", "inLanguage": "zh-TW",
          "url": f"{SITE_URL}/{rec['slug']}/", "hasMenuItem": offers}
    areas = "".join(f"<li><b>{esc(l)}</b>：{esc(rec['areas'].get(l, ''))}</li>" for l in lists)
    notes = "".join(f"<li>{esc(n.lstrip('• '))}</li>" for n in rec.get("notes_official", []))
    changed = f"．價錢上次變動 {rec['changed']}" if rec.get("changed") and rec["changed"] != rec.get("first_seen") else ""
    desc = (f"{name}全品項價格：{'、'.join(lists)}分開列" if len(lists) > 1 else f"{name}全品項價格（{len(items)} 品項）") \
        + ("，附官網標示的熱量與糖量" if has_nut else "") + f"。照官網菜單頁原文整理，{day} 查證。"
    return (head(f"{name}菜單價格 {day[:4]}（官網原文，{day} 查證）| Menu Check", desc, ld)
            + f'<p class="meta"><a href="../">Menu Check 台灣連鎖菜單</a></p>\n<h1>{esc(name)} 菜單價格</h1>\n'
            + f'<p class="meta">照<a href="{esc(rec["source_url"])}" rel="nofollow">官網菜單頁</a>原文整理．{day} 查證{changed}．價格以門市為準</p>\n'
            + (f"<p>{esc(name)}有{len(lists)}種價目，看你在哪裡買：</p>\n<ul>{areas}</ul>\n" if len(lists) > 1 else "")
            + '<div class="wrap"><table>\n<thead><tr><th>品項</th>'
            + "".join(f"<th>{esc(l)}</th>" for l in lists)
            + ("<th>熱量／糖量（官網標示，大杯）</th>" if has_nut else "") + ("<th>官網標示</th>" if has_note else "")
            + "</tr></thead>\n<tbody>" + "".join(rows) + "</tbody></table></div>\n"
            + f"<h2>官網上的其他說明</h2><ul>{notes}</ul>\n<p><small>{esc(rec.get('notes_zh', ''))}</small></p>\n"
            + "<p><small>本頁每天自動對官網重查一次；只轉成文字，不放店家照片。發現價格跟門市不同，歡迎告訴我們。</small></p>\n"
            + f"<p><small>Menu Check 不是{esc(name)}的官方網站，跟品牌沒有合作關係。</small></p>\n"
            + f"</main>{GOAT}</body></html>\n")


def build(root):
    root = Path(root)
    docs = root / "docs"
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "data").glob("*.json"))]
    for rec in recs:
        out = docs / rec["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(chain_page(rec), encoding="utf-8", newline="\n")
    items = "".join(f'<li><a href="{esc(r["slug"])}/">{esc(r["name_zh"])} 菜單價格</a> '
                    f'<small>（{sum(len(s["items"]) for s in r["sections"])} 品項，'
                    + (esc(shop_dated(r)) if is_shop(r) else f'{esc(r["checked"])} 查證') + "）</small></li>"
                    for r in recs)
    shops = any(is_shop(r) for r in recs)  # the wording only changes once a page from a restaurant's own menu exists
    own = "店家傳來或自己公布的菜單" if any(is_posted(r) for r in recs) else "店家自己傳來的菜單"
    top = (head("台灣餐廳與連鎖店菜單價格（官網原文、店家提供）| Menu Check",
                f"台灣餐廳與連鎖店的菜單價格：連鎖店照官網原文每天自動重查，其他店用{own}抄成文字，每頁寫出處和日期。")
           + "<h1>台灣餐廳與連鎖店菜單價格</h1>\n<p class=\"meta\">連鎖店照官網原文整理、每天自動重查；"
           + f"其他店用{own}抄成文字。每一頁都寫出處和日期。</p>\n") if shops else (
        head("台灣連鎖店菜單價格（官網原文，每天查證）| Menu Check",
             "台灣連鎖飲料店與餐廳的官方菜單價格，照官網原文整理、分地區價目、每天自動重查。")
        + "<h1>台灣連鎖店菜單價格</h1>\n<p class=\"meta\">每一頁都照該品牌官網原文整理，寫出處和查證日期，每天自動重查。</p>\n")
    who = "店家" if shops else "品牌"
    (docs / "index.html").write_text(
        top + f"<ul>{items}</ul>\n<p><small>Menu Check 不是這些{who}的官方網站，跟{who}沒有合作關係。</small></p>\n"
        + f"</main>{GOAT}</body></html>\n", encoding="utf-8", newline="\n")
    urls = [(f"{SITE_URL}/", max(r["checked"] for r in recs))] + [(f"{SITE_URL}/{r['slug']}/", r["checked"]) for r in recs]
    (docs / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n",
        encoding="utf-8", newline="\n")
    (docs / "llms.txt").write_text(
        ("# Menu Check 台灣\n\n台灣餐廳與連鎖店的菜單價格（新台幣）：連鎖店照官網原文整理、每天自動重查；"
         f"其他店用{own}抄成文字。每頁寫出處與日期。\n\n" if shops else
         "# Menu Check 台灣\n\n台灣連鎖店的官方菜單價格（新台幣），照官網原文整理，每天自動重查；每頁寫出處網址與查證日期。\n\n")
        + "".join(f"- [{r['name_zh']}]({SITE_URL}/{r['slug']}/): "
                  + ((f"店家公布的菜單（{r['checked']} 查證）" if is_posted(r) else f"店家提供的菜單（{r['checked']}）")
                     if is_shop(r) else r["source_url"]) + "\n" for r in recs),
        encoding="utf-8", newline="\n")
    return [u for u, _ in urls]
