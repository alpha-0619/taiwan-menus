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
    return " ".join(f"{k} {v}" for k, v in p.items()) if p else "—"


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


def chain_page(rec):
    lists, name, day = rec["price_lists"], rec["name_zh"], rec["checked"]
    rows, offers = [], []
    for s in rec["sections"]:
        rows.append(f'<tr class="sec"><th colspan="{len(lists) + 2}">{esc(s["name"])}</th></tr>')
        for it in s["items"]:
            nut = nutrition(it.get("nutrition", []))
            nut_txt = (f"{nut[2]} kcal / 糖 {nut[1]} g" + ("" if nut[0] == "大杯" else "（中杯）")) if nut else "—"
            rows.append("<tr><td>" + esc(it["name_zh"]) + "</td>"
                        + "".join(f"<td>{esc(cell(it['prices_by_list'].get(l)))}</td>" for l in lists)
                        + f"<td>{esc(nut_txt)}</td></tr>")
            for size, price in (it["prices_by_list"].get(lists[0]) or {}).items():
                offers.append({"@type": "MenuItem", "name": f"{it['name_zh']}（{size}）",
                               "offers": {"@type": "Offer", "price": price, "priceCurrency": "TWD",
                                          "description": f"{lists[0]}價格"}})
    ld = {"@context": "https://schema.org", "@type": "Menu", "name": f"{name} 菜單", "inLanguage": "zh-TW",
          "url": f"{SITE_URL}/{rec['slug']}/", "hasMenuItem": offers}
    areas = "".join(f"<li><b>{esc(l)}</b>：{esc(rec['areas'].get(l, ''))}</li>" for l in lists)
    notes = "".join(f"<li>{esc(n.lstrip('• '))}</li>" for n in rec.get("notes_official", []))
    changed = f"．價錢上次變動 {rec['changed']}" if rec.get("changed") and rec["changed"] != rec.get("first_seen") else ""
    return (head(f"{name}菜單價格 {day[:4]}（官網原文，{day} 查證）| Menu Check",
                 f"{name}全品項價格：{'、'.join(lists)}分開列，附官網標示的熱量與糖量。照官網菜單頁原文整理，{day} 查證。", ld)
            + f'<p class="meta"><a href="../">Menu Check 台灣連鎖菜單</a></p>\n<h1>{esc(name)} 菜單價格</h1>\n'
            + f'<p class="meta">照<a href="{esc(rec["source_url"])}" rel="nofollow">官網菜單頁</a>原文整理．{day} 查證{changed}．價格以門市為準</p>\n'
            + f"<p>{esc(name)}有{len(lists)}種價目，看你在哪裡買：</p>\n<ul>{areas}</ul>\n"
            + '<div class="wrap"><table>\n<thead><tr><th>品項</th>'
            + "".join(f"<th>{esc(l)}</th>" for l in lists)
            + "<th>熱量／糖量（官網標示，大杯）</th></tr></thead>\n<tbody>" + "".join(rows) + "</tbody></table></div>\n"
            + f"<h2>官網上的其他說明</h2><ul>{notes}</ul>\n<p><small>{esc(rec.get('notes_zh', ''))}</small></p>\n"
            + "<p><small>本頁每天自動對官網重查一次；只轉成文字，不放店家照片。發現價格跟門市不同，歡迎告訴我們。</small></p>\n"
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
                    f'<small>（{sum(len(s["items"]) for s in r["sections"])} 品項，{esc(r["checked"])} 查證）</small></li>'
                    for r in recs)
    (docs / "index.html").write_text(
        head("台灣連鎖店菜單價格（官網原文，每天查證）| Menu Check",
             "台灣連鎖飲料店與餐廳的官方菜單價格，照官網原文整理、分地區價目、每天自動重查。")
        + "<h1>台灣連鎖店菜單價格</h1>\n<p class=\"meta\">每一頁都照該品牌官網原文整理，寫出處和查證日期，每天自動重查。</p>\n"
        + f"<ul>{items}</ul>\n</main>{GOAT}</body></html>\n", encoding="utf-8", newline="\n")
    urls = [(f"{SITE_URL}/", max(r["checked"] for r in recs))] + [(f"{SITE_URL}/{r['slug']}/", r["checked"]) for r in recs]
    (docs / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{u}</loc><lastmod>{d}</lastmod></url>\n" for u, d in urls) + "</urlset>\n",
        encoding="utf-8", newline="\n")
    (docs / "llms.txt").write_text(
        "# Menu Check 台灣\n\n台灣連鎖店的官方菜單價格（新台幣），照官網原文整理，每天自動重查；每頁寫出處網址與查證日期。\n\n"
        + "".join(f"- [{r['name_zh']}]({SITE_URL}/{r['slug']}/): {r['source_url']}\n" for r in recs),
        encoding="utf-8", newline="\n")
    return [u for u, _ in urls]
