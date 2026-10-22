"""Daily update: re-read each chain's official menu page, keep the data only when it passes the checks, rebuild docs/.

Usage:  python update.py [--offline]      (--offline: rebuild docs/ from data/ without fetching)
For each chain: fetch the official page, parse it, and check that every price line sits under its item in the
official text. A page that fails to load or parse, fails that check, or suddenly lists far fewer items keeps the
old data (nothing wrong is published) and the run ends with exit code 1, so GitHub marks it failed and emails.
Unchanged prices only move the check date forward; changed prices also move the 'changed' date and are logged.
"""
import json
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tw import kebuke, louisa, pages

ROOT = Path(__file__).resolve().parent
CHAINS = [kebuke, louisa]
UA = {"User-Agent": "Mozilla/5.0 (compatible; MenuCheckBot/1.0; +https://alpha-0619.github.io/taiwan-menus/)"}


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
        return r.read()


def read_chain(chain):
    """A chain with one menu page has URL; one with a page per category has URLS (fetched one at a time)."""
    if hasattr(chain, "URLS"):
        raws = {}
        for n, url in enumerate(chain.URLS):
            if n:
                time.sleep(1.5)
            raws[url] = fetch(url)
        return chain.parse(raws)
    return chain.parse(fetch(chain.URL))


def priced(rec):
    return [(s["name"], it["name_zh"], json.dumps(it["prices_by_list"], ensure_ascii=False, sort_keys=True))
            for s in rec["sections"] for it in s["items"]]


def main():
    today = datetime.now(timezone(timedelta(hours=8))).date().isoformat()  # Taiwan: UTC+8, no daylight saving
    failed = []
    for chain in CHAINS:
        path = ROOT / "data" / f"{chain.SLUG}.json"
        old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
        if "--offline" in sys.argv:
            continue
        try:
            rec, text = read_chain(chain)
            n_new = sum(len(s["items"]) for s in rec["sections"])
            n_old = sum(len(s["items"]) for s in old["sections"]) if old else 0
            bad = chain.check(rec, text)
            if bad:
                raise ValueError(f"price lines not under their item in the official text: {bad[:5]}")
            if n_new < 20 or (n_old and n_new < 0.7 * n_old):
                raise ValueError(f"only {n_new} items (was {n_old}): the page may have changed shape")
        except Exception as e:  # noqa: BLE001  keep the old data, report, go on with the next chain
            failed.append(f"{chain.SLUG}: {type(e).__name__}: {e}")
            continue
        same = old is not None and priced(old) == priced(rec)
        rec["first_seen"] = (old or {}).get("first_seen", today)
        rec["changed"] = old["changed"] if same else today
        rec["checked"] = today
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
        (ROOT / "snapshots").mkdir(exist_ok=True)
        (ROOT / "snapshots" / f"{chain.SLUG}.txt").write_text(text, encoding="utf-8", newline="\n")
        if not same and old is not None:
            before, after = set(priced(old)), set(priced(rec))
            with (ROOT / "data" / "changes.log").open("a", encoding="utf-8", newline="\n") as log:
                log.write(f"{today} {chain.SLUG}: {len(after - before)} new or changed, {len(before - after)} gone\n")
        print(f"{chain.SLUG}: {'unchanged' if same else 'CHANGED'}, {sum(len(s['items']) for s in rec['sections'])} items, checked {today}")
    urls = pages.build(ROOT)
    print(f"built {len(urls)} pages")
    if failed:
        print("FAILED (old data kept):\n  " + "\n  ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    main()
