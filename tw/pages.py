"""Build docs/ (the published site) from data/*.json: one page per chain, the home page, sitemap.xml, llms.txt."""
import html
import json
import re
from pathlib import Path

SITE_URL = "https://alpha-0619.github.io/taiwan-menus"
HOME = "https://alpha-0619.github.io/"  # the page linking every Menu Check site, with About and Privacy
FOOT = {"zh": ("關於 Menu Check", "隱私權政策"), "en": ("About Menu Check", "Privacy policy"),
        "ja": ("Menu Checkについて", "プライバシーポリシー"), "ko": ("Menu Check 소개", "개인정보 처리방침")}
GOAT ='<script data-goatcounter="https://menucheck.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'
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


def price_range(price_dicts):
    """'價錢從 60 元到 390 元' needs the lowest and highest price; an add-on ('加價') is not a price of its own."""
    vals = [v for p in price_dicts for k, v in (p or {}).items() if k != "加價"]
    return (min(vals), max(vals)) if vals else None


def nutrition(lines):
    """('大杯', sugar, kcal) as printed; the 中杯 line when only a medium is sold."""
    for size in ("大杯", "中杯"):
        for i, line in enumerate(lines):
            if line.startswith(f"【{size}】") and i + 1 < len(lines):
                m = re.search(r"糖量：\s*([\d.]+)\s*g\s*；\s*熱量：\s*([\d.]+)\s*[Kk]cal", lines[i + 1])
                if m:
                    return size, m.group(1), m.group(2)
    return None


def head(title, desc, ld=None, lang="zh-Hant-TW", alts=(), css=""):
    return (f'<!doctype html>\n<html lang="{lang}"><head><meta charset="utf-8">\n'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">\n<title>{esc(title)}</title>\n'
            f'<meta name="description" content="{esc(desc)}">\n'
            + "".join(f'<link rel="alternate" hreflang="{h}" href="{esc(u)}">\n' for h, u in alts)
            + (f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n' if ld else "")
            + f"<style>{STYLE}{css}</style></head><body><main>\n")


def foot_links(lang="zh"):
    """About and Privacy, on every page (AdSense asks for clear navigation and a privacy policy)."""
    about, privacy = FOOT[lang]
    return f'<p><small><a href="{HOME}about/">{about}</a> · <a href="{HOME}privacy/">{privacy}</a></small></p>\n'


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

# Pages in a visitor's language, made only where the shop itself wrote every dish name in that language.
LANG = {"en": "English", "ja": "日本語", "ko": "한국어"}
CITY = {"台北": {"en": "Taipei", "ja": "台北", "ko": "타이베이"}, "台南": {"en": "Tainan", "ja": "台南", "ko": "타이난"},
        "花蓮": {"en": "Hualien", "ja": "花蓮", "ko": "화롄"}}
SIZE = {"en": {"大": "Large", "中": "Medium", "小": "Small"}, "ja": {"大": "大", "中": "中", "小": "小"},
        "ko": {"大": "대", "中": "중", "小": "소"}}
LANG_CSS = ("td:not(:first-child){white-space:normal} .zh{font-size:1.15rem;font-weight:600}"
            "main{padding-bottom:96px} [hidden]{display:none!important}"
            "button{font:inherit;color:var(--fg);background:var(--sec);border:1px solid var(--line);border-radius:6px;"
            "padding:6px 10px;cursor:pointer} button.add{display:block;margin:0 0 4px;white-space:nowrap}"
            "#bar{position:fixed;left:0;right:0;bottom:0;z-index:5;display:flex;flex-wrap:wrap;gap:8px;align-items:center;"
            "padding:10px 16px;background:var(--bg);border-top:1px solid var(--line)} #bar span{flex:1 1 auto}"
            "#card{position:fixed;inset:0;z-index:6;overflow:auto;padding:16px;background:var(--bg)}"
            ".big{font-size:1.7rem;font-weight:700;margin:.4em 0} #lines{list-style:none;padding:0}"
            "#lines li{display:grid;grid-template-columns:1fr auto auto auto;gap:8px;align-items:center;font-size:1.5rem;"
            "padding:8px 0;border-bottom:1px solid var(--line)} #lines .zhl{font-weight:700}"
            "#lines button{min-width:44px;min-height:44px}")

# The order screen: a visitor taps prices, then shows the staff their dishes in Chinese with the total.
ORDER = {
    "en": {"tap": "Tap a price to add the dish to your order. The order screen lists your dishes in Chinese, "
                  "ready to show the staff.",
           "bar": "Your order", "item": "item", "items": "items", "show": "Show the staff", "clear": "Clear",
           "hint": "Show this screen to the staff.", "close": "Back to the menu",
           "note": "The total adds up the prices on this page; the price at the shop is final.",
           "less": "One less", "more": "One more"},
    "ja": {"tap": "料金をタップすると注文リストに入ります。注文画面には料理名が中国語で出るので、そのまま店員に見せられます。",
           "bar": "注文リスト", "item": "品", "items": "品", "show": "店員に見せる", "clear": "クリア",
           "hint": "この画面を店員に見せてください。", "close": "メニューに戻る",
           "note": "合計はこのページの料金を足したものです。お店の表示価格が優先です。",
           "less": "1つ減らす", "more": "1つ増やす"},
    "ko": {"tap": "가격을 누르면 주문 목록에 들어갑니다. 주문 화면에는 메뉴 이름이 중국어로 나와서 그대로 직원에게 보여 줄 수 있습니다.",
           "bar": "주문 목록", "item": "개", "items": "개", "show": "직원에게 보여 주기", "clear": "지우기",
           "hint": "이 화면을 직원에게 보여 주세요.", "close": "메뉴로 돌아가기",
           "note": "합계는 이 페이지의 가격을 더한 것입니다. 가게에 표시된 가격이 우선입니다.",
           "less": "하나 빼기", "more": "하나 더"},
}
ORDER_JS = """(function () {
  var T = JSON.parse(document.getElementById("order-text").textContent), order = [];
  var bar = document.getElementById("bar"), sum = document.getElementById("sum"), card = document.getElementById("card");
  var lines = document.getElementById("lines"), tot = document.getElementById("tot");
  function draw() {
    var n = 0, s = 0;
    order = order.filter(function (o) { return o.q > 0; });
    lines.textContent = "";
    order.forEach(function (o) {
      n += o.q; s += o.q * o.p;
      var li = document.createElement("li"), name = document.createElement("span"), pr = document.createElement("span");
      name.className = "zhl"; name.lang = "zh-Hant"; name.textContent = o.zh + " \\u00d7 " + o.q;
      pr.textContent = o.q * o.p;
      li.appendChild(name); li.appendChild(pr);
      [["\\u2212", -1, T.less], ["+", 1, T.more]].forEach(function (b) {
        var btn = document.createElement("button");
        btn.type = "button"; btn.textContent = b[0]; btn.setAttribute("aria-label", b[2] + ": " + o.zh);
        btn.onclick = function () { o.q += b[1]; draw(); };
        li.appendChild(btn);
      });
      lines.appendChild(li);
    });
    tot.textContent = "\\u5408\\u8a08 " + s + " \\u5143";
    sum.textContent = T.bar + ": " + n + " " + (n === 1 ? T.item : T.items) + " \\u00b7 NT$ " + s;
    bar.hidden = n === 0;
    if (n === 0) card.hidden = true;
  }
  Array.prototype.forEach.call(document.querySelectorAll("button.add"), function (b) {
    b.onclick = function () {
      var o = order.filter(function (x) { return x.zh === b.getAttribute("data-zh"); })[0];
      if (o) o.q += 1; else order.push({zh: b.getAttribute("data-zh"), p: Number(b.getAttribute("data-p")), q: 1});
      draw();
    };
  });
  document.getElementById("show").onclick = function () { card.hidden = false; };
  document.getElementById("close").onclick = function () { card.hidden = true; };
  document.getElementById("clr").onclick = function () { order = []; draw(); };
})();"""


def page_langs(rec):
    """Languages the shop gave every dish name in, for shops whose own name and city we have in that language."""
    items = [it for s in rec["sections"] for it in s["items"]]
    return [l for l in LANG if is_shop(rec) and rec.get(f"name_{l}") and rec["city"] in CITY
            and all(it.get(f"name_{l}") for it in items)]


def alts(rec):
    """hreflang links between a shop's Chinese page and its pages in other languages (none if it has none)."""
    langs = page_langs(rec)
    return ((("zh-Hant-TW", f"{SITE_URL}/{rec['slug']}/"),) + tuple((l, f"{SITE_URL}/{l}/{rec['slug']}/") for l in langs)
            if langs else ())


def cell_lang(p, lang):
    """{'大': 70, '小': 35} -> 'Large 70 / Small 35'; {'10個': 70, '1個': 7} -> '70 (10 pcs) / 7 (1 pc)'."""
    if not p:
        return "—"
    out = []
    for k, v in p.items():
        n = re.fullmatch(r"(\d+)個", k)
        if k == "單價":
            out.append(f"{v}")
        elif k in SIZE[lang]:
            out.append(f"{SIZE[lang][k]} {v}")
        elif n:
            count = {"en": f"{n.group(1)} pc" + ("" if n.group(1) == "1" else "s"), "ja": f"{n.group(1)}個",
                     "ko": f"{n.group(1)}개"}[lang]
            out.append(f"{v} ({count})")
        else:
            raise ValueError(f"no {lang} label for the price {k!r} in {p}")
    return " / ".join(out)


def price_buttons(p, lang, zh):
    """One button per price, labelled as cell_lang writes it ('+ Large 70'); data-zh is what the order screen
    shows the staff ('牛肉麵（大）')."""
    if not p:
        return "—"
    return "".join(f'<button type="button" class="add" data-zh="{esc(zh if k == "單價" else f"{zh}（{k}）")}" '
                   f'data-p="{v}">+ {esc(cell_lang({k: v}, lang))}</button>' for k, v in p.items())


def lang_text(lang, rec, n):
    """The fixed sentences of a shop page in a visitor's language."""
    name, zh, city, day = rec[f"name_{lang}"], rec["name_zh"], CITY[rec["city"]][lang], rec["checked"]
    addr, posted = rec.get("address", ""), is_posted(rec)
    if lang == "en":
        return {"title": f"{name} menu & prices {day[:4]}, {city} (the shop's own English menu) | Menu Check",
                "desc": f"{name} ({zh}), {city}: the shop's own English menu with prices in NT$ ({n} items), "
                        f"typed out as text. Checked {day}.",
                "h1": f"{name} menu & prices",
                "where": f"{zh} · {city} · Address in Chinese (show it to your driver): {addr}", "phone": "Phone",
                "src": (f"From the menu the shop posted on its own Facebook page, typed out as text (checked {day})."
                        if posted else f"From the menu the shop gave us on {day}, typed out as text.")
                       + " The English dish names are the shop's own. Prices in NT$; the price at the shop is final.",
                "th": ("Dish (the shop's English; show the staff the Chinese under it)", "Price (NT$)"),
                "foot": f"Text only, no photos. Menu Check is not the official site of {name} "
                        "and has no connection with the shop.",
                "menu": f"{name} menu"}
    if lang == "ja":
        return {"title": f"{name}のメニューと料金 {day[:4]}（{city}・お店の日本語メニュー）｜Menu Check",
                "desc": f"{city}の{name}：お店自身の日本語メニューと料金（台湾ドル・{n}品）を文字にしました。{day}確認。",
                "h1": f"{name} メニューと料金",
                "where": f"{zh}・{city}・住所（中国語。タクシーで見せる用）：{addr}", "phone": "電話",
                "src": (f"お店が自分のFacebookページに載せたメニューを文字にしました（{day}確認）。"
                        if posted else f"{day}にお店からもらったメニューを文字にしました。")
                       + "日本語の料理名はお店自身の翻訳です。料金は台湾ドル（NT$）で、お店の表示価格が優先です。",
                "th": ("料理（お店の日本語。注文時は下の中国語を指さし）", "料金（NT$）"),
                "foot": f"写真はなく、文字だけです。Menu Checkは{name}の公式サイトではなく、お店とは関係ありません。",
                "menu": f"{name} メニュー"}
    return {"title": f"{name} 메뉴와 가격 {day[:4]} ({city}, 가게의 한국어 메뉴) | Menu Check",
            "desc": f"{city} {name}: 가게가 직접 만든 한국어 메뉴와 가격(대만 달러, {n}개)을 글자로 옮겼습니다. {day} 확인.",
            "h1": f"{name} 메뉴와 가격",
            "where": f"{zh} · {city} · 주소(중국어, 택시 기사에게 보여 주세요): {addr}", "phone": "전화",
            "src": (f"가게가 자기 페이스북 페이지에 올린 메뉴를 글자로 옮겼습니다({day} 확인). "
                    if posted else f"{day}에 가게에서 받은 메뉴를 글자로 옮겼습니다. ")
                   + "한국어 메뉴 이름은 가게가 직접 번역한 것입니다. 가격은 대만 달러(NT$)이며, 가게에 표시된 가격이 우선입니다.",
            "th": ("메뉴(가게의 한국어, 주문할 때 아래 중국어를 가리키세요)", "가격(NT$)"),
            "foot": f"사진 없이 글자만 있습니다. Menu Check는 {name}의 공식 사이트가 아니며 가게와 관련이 없습니다.",
            "menu": f"{name} 메뉴"}


LANG_INDEX = {
    "en": {"title": "Taiwan restaurant menus in English, from the shops | Menu Check",
           "h1": "Taiwan restaurant menus in English",
           "intro": "Menus the restaurants sent us or posted themselves, typed out as text, with the shop's own English "
                    "dish names and prices in NT$. Each page says where the menu came from and when we checked it.",
           "item": lambda zh, city, n: f"({zh}, {city}, {n} items)", "nav": "Taiwan",
           "order": "On each page, tap the prices of what you want: the order screen lists it in Chinese with the total, "
                    "ready to show the staff.",
           "foot": "Menu Check is not the official site of these restaurants and has no connection with them."},
    "ja": {"title": "台湾の飲食店メニュー（お店の日本語）｜Menu Check",
           "h1": "台湾の飲食店メニュー（日本語）",
           "intro": "お店から送ってもらった、またはお店が自分で載せたメニューを文字にしました。お店自身の日本語の料理名と、"
                    "台湾ドルの料金がついています。各ページに出所と確認日を書いています。",
           "item": lambda zh, city, n: f"（{zh}・{city}・{n}品）", "nav": "台湾",
           "order": "各ページで料金をタップすると注文リストに入り、注文画面に料理名が中国語で合計と一緒に出るので、そのまま店員に見せられます。",
           "foot": "Menu Checkはこれらのお店の公式サイトではなく、お店とは関係ありません。"},
    "ko": {"title": "대만 식당 메뉴 (가게의 한국어) | Menu Check",
           "h1": "대만 식당 메뉴 (한국어)",
           "intro": "가게가 보내 주거나 직접 올린 메뉴를 글자로 옮겼습니다. 가게가 직접 번역한 한국어 메뉴 이름과 "
                    "대만 달러 가격이 있습니다. 각 페이지에 출처와 확인 날짜를 적었습니다.",
           "item": lambda zh, city, n: f"({zh}, {city}, {n}개)", "nav": "대만",
           "order": "각 페이지에서 가격을 누르면 주문 목록에 들어가고, 주문 화면에 메뉴 이름이 중국어로 합계와 함께 나와서 그대로 직원에게 보여 줄 수 있습니다.",
           "foot": "Menu Check는 이 가게들의 공식 사이트가 아니며 가게와 관련이 없습니다."},
}


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
    other = " · ".join(f'<a href="../{l}/{rec["slug"]}/" hreflang="{l}" lang="{l}">{LANG[l]}</a>' for l in page_langs(rec))
    other = f'<p class="meta">店家自己的外文菜單：{other}</p>\n' if other else ""
    rng = price_range(it.get("prices") for it in items)
    sized = any(len([k for k in (it.get("prices") or {}) if k != "加價"]) > 1 for it in items)
    summary = (f"這份菜單共 {len(items)} 個品項" + (f"，價錢從 {rng[0]:,} 元到 {rng[1]:,} 元" if rng else "")
               + ("，有些品項分不同份量" if sized else "") + "。"
               + (f"店家自己的菜單上有{'、'.join(langs)}文菜名，表格裡一併列出。" if langs else ""))
    return (head(f"{city}美食》{name}最新菜單價格 {day[:4]}（{title_src}）| Menu Check", desc, ld, alts=alts(rec))
            + f'<p class="meta"><a href="{HOME}">Menu Check</a> › <a href="../">台灣菜單</a></p>\n<h1>{esc(name)} 最新菜單價格</h1>\n'
            + f'<p class="meta">{where}{esc(rec["provided"])}．價格以店內為準</p>\n' + info + other
            + f"<p>{esc(summary)}</p>\n"
            + '<div class="wrap"><table style="min-width:0">\n<thead><tr><th>品項'
            + (f"（店家寫的{'、'.join(langs)}文）" if langs else "") + "</th><th>價格（新台幣）</th></tr></thead>\n<tbody>"
            + "".join(rows) + "</tbody></table></div>\n"
            + f"<p><small>{foot}</small></p>\n"
            + f"<p><small>Menu Check 不是{esc(name)}的官方網站，跟店家沒有合作關係。</small></p>\n"
            + foot_links() + f"</main>{GOAT}</body></html>\n")


def shop_page_lang(rec, lang):
    """The same menu in a visitor's language: the shop's own dish name, the Chinese to point at, the price."""
    items = [it for s in rec["sections"] for it in s["items"]]
    t, slug = lang_text(lang, rec, len(items)), rec["slug"]
    rows, offers = [], []
    for s in rec["sections"]:
        rows.append(f'<tr class="sec"><th colspan="2">{esc(s.get(f"name_{lang}") or s["name"])}</th></tr>')
        for it in s["items"]:
            rows.append(f"<tr><td>{esc(it[f'name_{lang}'])}<br><span lang=\"zh-Hant\" class=\"zh\">{esc(it['name_zh'])}</span>"
                        f"</td><td>{price_buttons(it.get('prices'), lang, it['name_zh'])}</td></tr>")
            for size, price in (it.get("prices") or {}).items():
                offers.append({"@type": "MenuItem", "name": it[f"name_{lang}"], "alternateName": it["name_zh"],
                               "offers": {"@type": "Offer", "price": price, "priceCurrency": "TWD",
                                          "description": cell_lang({size: price}, lang)}})
    ld = {"@context": "https://schema.org", "@type": "Menu", "name": t["menu"], "inLanguage": lang,
          "url": f"{SITE_URL}/{lang}/{slug}/", "hasMenuItem": offers}
    others = " · ".join([f'<a href="../../{slug}/" hreflang="zh-Hant-TW" lang="zh-Hant-TW">中文</a>']
                        + [f'<a href="../../{l}/{slug}/" hreflang="{l}" lang="{l}">{LANG[l]}</a>'
                           for l in page_langs(rec) if l != lang])
    phone = f" · {t['phone']}: {esc(rec['phone'])}" if rec.get("phone") else ""
    rng = price_range(it.get("prices") for it in items)
    summary = ({"en": "This menu has {n} dishes, from NT${lo:,} to NT${hi:,}.",
                "ja": "このメニューは{n}品、料金は{lo:,}〜{hi:,}台湾ドルです。",
                "ko": "이 메뉴는 {n}개이며, 가격은 {lo:,}~{hi:,} 대만 달러입니다."}[lang].format(n=len(items), lo=rng[0], hi=rng[1])
               if rng else "")
    o = ORDER[lang]
    order = (f'<div id="card" hidden role="dialog" aria-modal="true" aria-labelledby="card-h">'
             f'<p class="meta" id="card-h">{esc(o["hint"])}</p>\n<p class="big" lang="zh-Hant">你好，我要點：</p>\n'
             f'<ul id="lines"></ul>\n<p class="big" id="tot" lang="zh-Hant"></p>\n'
             f'<p lang="zh-Hant"><small>照網頁上的價錢算，以店內為準</small></p>\n<p><small>{esc(o["note"])}</small></p>\n'
             f'<button type="button" id="close">{esc(o["close"])}</button></div>\n'
             f'<div id="bar" hidden><span id="sum" aria-live="polite"></span>'
             f'<button type="button" id="show">{esc(o["show"])}</button><button type="button" id="clr">{esc(o["clear"])}</button></div>\n'
             f'<script type="application/json" id="order-text">'
             + json.dumps(o, ensure_ascii=False).replace("</", "<\\/") + f"</script>\n<script>{ORDER_JS}</script>\n")
    return (head(t["title"], t["desc"], ld, lang, alts(rec), LANG_CSS)
            + f'<p class="meta"><a href="{HOME}">Menu Check</a> › <a href="../">{esc(LANG_INDEX[lang]["nav"])}</a> · {others}</p>\n'
            + f'<h1>{esc(t["h1"])}</h1>\n'
            + f'<p class="meta">{esc(t["where"])}{phone}</p>\n<p class="meta">{esc(t["src"])}</p>\n'
            + (f"<p>{esc(summary)}</p>\n" if summary else "")
            + f'<p class="meta">{esc(o["tap"])}</p>\n'
            + '<div class="wrap"><table style="min-width:0">\n<thead><tr>'
            + "".join(f"<th>{esc(h)}</th>" for h in t["th"]) + "</tr></thead>\n<tbody>" + "".join(rows)
            + "</tbody></table></div>\n"
            + f"<p><small>{esc(t['foot'])}</small></p>\n" + foot_links(lang) + f"</main>{order}{GOAT}</body></html>\n")


def lang_index(lang, recs):
    """The list of shops that have a page in this language."""
    t = LANG_INDEX[lang]
    items = "".join(f'<li><a href="{esc(r["slug"])}/">{esc(r[f"name_{lang}"])}</a> <small>'
                    + esc(t["item"](r["name_zh"], CITY[r["city"]][lang], sum(len(s["items"]) for s in r["sections"])))
                    + "</small></li>" for r in recs)
    return (head(t["title"], t["intro"], lang=lang)
            + f'<p class="meta"><a href="{HOME}">Menu Check</a> › '
            + '<a href="../" hreflang="zh-Hant-TW" lang="zh-Hant-TW">台灣菜單（中文）</a></p>\n'
            + f'<h1>{esc(t["h1"])}</h1>\n<p class="meta">{esc(t["intro"])}</p>\n<p>{esc(t["order"])}</p>\n<ul>{items}</ul>\n'
            + f"<p><small>{esc(t['foot'])}</small></p>\n" + foot_links(lang) + f"</main>{GOAT}</body></html>\n")


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
    rng = price_range(it["prices_by_list"].get(l) for it in items for l in lists)
    summary = f"官網列出 {len(items)} 個品項" + (f"，價錢從 {rng[0]:,} 元到 {rng[1]:,} 元" if rng else "") + "。"
    desc = (f"{name}全品項價格：{'、'.join(lists)}分開列" if len(lists) > 1 else f"{name}全品項價格（{len(items)} 品項）") \
        + ("，附官網標示的熱量與糖量" if has_nut else "") + f"。照官網菜單頁原文整理，{day} 查證。"
    return (head(f"{name}菜單價格 {day[:4]}（官網原文，{day} 查證）| Menu Check", desc, ld)
            + f'<p class="meta"><a href="{HOME}">Menu Check</a> › <a href="../">台灣菜單</a></p>\n<h1>{esc(name)} 菜單價格</h1>\n'
            + f'<p class="meta">照<a href="{esc(rec["source_url"])}" rel="nofollow">官網菜單頁</a>原文整理．{day} 查證{changed}．價格以門市為準</p>\n'
            + f"<p>{esc(summary)}</p>\n"
            + (f"<p>{esc(name)}有{len(lists)}種價目，看你在哪裡買：</p>\n<ul>{areas}</ul>\n" if len(lists) > 1 else "")
            + '<div class="wrap"><table>\n<thead><tr><th>品項</th>'
            + "".join(f"<th>{esc(l)}</th>" for l in lists)
            + ("<th>熱量／糖量（官網標示，大杯）</th>" if has_nut else "") + ("<th>官網標示</th>" if has_note else "")
            + "</tr></thead>\n<tbody>" + "".join(rows) + "</tbody></table></div>\n"
            + f"<h2>官網上的其他說明</h2><ul>{notes}</ul>\n<p><small>{esc(rec.get('notes_zh', ''))}</small></p>\n"
            + "<p><small>本頁每天自動對官網重查一次；只轉成文字，不放店家照片。發現價格跟門市不同，歡迎告訴我們。</small></p>\n"
            + f"<p><small>Menu Check 不是{esc(name)}的官方網站，跟品牌沒有合作關係。</small></p>\n"
            + foot_links() + f"</main>{GOAT}</body></html>\n")


def build(root):
    root = Path(root)
    docs = root / "docs"
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((root / "data").glob("*.json"))]
    for rec in recs:
        out = docs / rec["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(chain_page(rec), encoding="utf-8", newline="\n")
    by_lang = {l: [r for r in recs if l in page_langs(r)] for l in LANG}
    for lang, lrecs in by_lang.items():
        for rec in lrecs:
            out = docs / lang / rec["slug"] / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(shop_page_lang(rec, lang), encoding="utf-8", newline="\n")
        if lrecs:
            (docs / lang / "index.html").write_text(lang_index(lang, lrecs), encoding="utf-8", newline="\n")
    lang_links = " · ".join(f'<a href="{l}/" hreflang="{l}" lang="{l}">{LANG[l]}</a>' for l in LANG if by_lang[l])
    lang_links = (f'<p class="meta">店家自己的外文菜單：{lang_links}</p>\n'
                  "<p>有店家自己英文、日文或韓文菜單的店，另外有外文頁：外國旅客在外文頁上按價錢點菜，"
                  "畫面會變成大字的中文點餐單和總價，可以直接拿給店員看。</p>\n") if lang_links else ""
    items = "".join(f'<li><a href="{esc(r["slug"])}/">{esc(r["name_zh"])} 菜單價格</a> '
                    f'<small>（{sum(len(s["items"]) for s in r["sections"])} 品項，'
                    + (esc(shop_dated(r)) if is_shop(r) else f'{esc(r["checked"])} 查證') + "）</small></li>"
                    for r in recs)
    shops = any(is_shop(r) for r in recs)  # the wording only changes once a page from a restaurant's own menu exists
    own = "店家傳來或自己公布的菜單" if any(is_posted(r) for r in recs) else "店家自己傳來的菜單"
    crumb = f'<p class="meta"><a href="{HOME}">Menu Check</a> › 台灣</p>\n'
    top = (head("台灣餐廳與連鎖店菜單價格（官網原文、店家提供）| Menu Check",
                f"台灣餐廳與連鎖店的菜單價格：連鎖店照官網原文每天自動重查，其他店用{own}抄成文字，每頁寫出處和日期。")
           + crumb + "<h1>台灣餐廳與連鎖店菜單價格</h1>\n<p class=\"meta\">連鎖店照官網原文整理、每天自動重查；"
           + f"其他店用{own}抄成文字。每一頁都寫出處和日期。</p>\n") if shops else (
        head("台灣連鎖店菜單價格（官網原文，每天查證）| Menu Check",
             "台灣連鎖飲料店與餐廳的官方菜單價格，照官網原文整理、分地區價目、每天自動重查。")
        + crumb + "<h1>台灣連鎖店菜單價格</h1>\n<p class=\"meta\">每一頁都照該品牌官網原文整理，寫出處和查證日期，每天自動重查。</p>\n")
    who = "店家" if shops else "品牌"
    (docs / "index.html").write_text(
        top + lang_links + f"<ul>{items}</ul>\n<p><small>Menu Check 不是這些{who}的官方網站，跟{who}沒有合作關係。</small></p>\n"
        + foot_links() + f"</main>{GOAT}</body></html>\n", encoding="utf-8", newline="\n")
    urls = [(f"{SITE_URL}/", max(r["checked"] for r in recs))] + [(f"{SITE_URL}/{r['slug']}/", r["checked"]) for r in recs]
    for lang, lrecs in by_lang.items():
        if lrecs:
            urls += [(f"{SITE_URL}/{lang}/", max(r["checked"] for r in lrecs))]
            urls += [(f"{SITE_URL}/{lang}/{r['slug']}/", r["checked"]) for r in lrecs]
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
                     if is_shop(r) else r["source_url"]) + "\n" for r in recs)
        + "".join(f"- [{r[f'name_{l}']}]({SITE_URL}/{l}/{r['slug']}/): {r['name_zh']}，店家自己的{LANG[l]}菜單（{r['checked']}）\n"
                  for l, lrecs in by_lang.items() for r in lrecs),
        encoding="utf-8", newline="\n")
    return [u for u, _ in urls]
