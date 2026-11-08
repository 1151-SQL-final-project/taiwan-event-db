"""核對從開放資料文字自動擷取的優惠：到活動官網找有沒有寫同樣的優惠與價格。

用法（在專案根目錄，先跑過 etl\\clean_moc.py、etl\\clean_opentix.py）：
    .venv\\Scripts\\python etl\\verify_discounts.py

只核對 OPENTIX 沒有提供的那些（OPENTIX 有結構化資料的會直接取代）。
每個網站先看 robots.txt 是否允許，每秒最多 1 個請求。

結果 data/review/discount_verification.csv 的 Status：
    官網核對通過     官網上同一段文字裡有優惠關鍵字，也有這個價格（或折數）；Evidence 欄是那段原文
    官網未找到       抓得到官網，但找不到對應的文字（可能寫在圖片裡、或官網改了）→ 需要人工看
    無法讀取官網     網站不允許程式讀取、要登入（例如 Facebook）、或連線失敗 → 需要人工看
    沒有官網網址     開放資料沒附網址；優惠文字本身就來自主辦單位提供給文化部的資料
"""
import csv
import html
import pathlib
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

ROOT = pathlib.Path(__file__).resolve().parent.parent
CLEAN, REVIEW = ROOT / "data" / "clean", ROOT / "data" / "review"
USER_AGENT = "Mozilla/5.0 (compatible; taiwan-event-db student project; NTNU SQL course)"
KEYWORDS = {"學生優惠": ["學生"], "早鳥優惠": ["早鳥"], "敬老優惠": ["敬老", "65", "六十五", "長者"], "團體優惠": ["團體"]}

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_pages: dict[str, str | None] = {}
_links: dict[str, list[str]] = {}
TICKET_LINK_WORDS = ("票價", "門票", "參觀資訊", "收費", "購票")
_last_request = 0.0


def polite_get(url: str) -> bytes:
    global _last_request
    time.sleep(max(0.0, 1.0 - (time.time() - _last_request)))
    _last_request = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def allowed(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc
    if host not in _robots:
        parser = urllib.robotparser.RobotFileParser()
        try:
            parser.parse(polite_get(f"https://{host}/robots.txt").decode("utf-8", "replace").splitlines())
        except Exception:
            parser = None  # 沒有 robots.txt 視為允許
        _robots[host] = parser
    parser = _robots[host]
    return parser is None or parser.can_fetch(USER_AGENT, url)


def page_text(url: str) -> str | None:
    if url in _pages:
        return _pages[url]
    text = None
    try:
        if "facebook.com" not in url and allowed(url):
            raw = polite_get(url)
            charset = re.search(rb'charset=["\']?([\w-]+)', raw[:2000])
            body = raw.decode(charset.group(1).decode() if charset else "utf-8", "replace")
            # 記下同網站裡「票價資訊」這類連結，官網首頁或活動頁找不到時再去那裡找
            host = urllib.parse.urlparse(url).netloc
            _links[url] = list(dict.fromkeys(
                urllib.parse.urljoin(url, href)
                for href, label in re.findall(r'(?is)<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', body)
                if any(w in re.sub(r"<[^>]+>", "", label) for w in TICKET_LINK_WORDS)
                and urllib.parse.urlparse(urllib.parse.urljoin(url, href)).netloc == host))[:3]
            body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", body)
            text = unicodedata.normalize("NFKC", html.unescape(re.sub(r"<[^>]+>", " ", body)))
            text = re.sub(r"\s+", " ", text)
    except (urllib.error.URLError, TimeoutError, ValueError, LookupError):
        text = None
    _pages[url] = text
    return text


def find_evidence(text: str, kind: str, price: int, description: str) -> str | None:
    """在官網文字中找：優惠關鍵字附近 80 字內，有這個價格（或說明裡的折數）。"""
    rate = re.search(r"(\d{1,2})\s*折", unicodedata.normalize("NFKC", description))
    # 數字一定要像價格（20元、NT$20、新臺幣20、$20、+20）或折數，避免把日期、月曆上的數字當成證據
    amount = rf"(?:{price:,}|{price})"
    patterns = [rf"(?<![\d,]){amount}\s*元", rf"(?:NT\$|\$|新臺幣|新台幣|\+)\s*{amount}(?![\d,])"]
    patterns += [rf"(?<!\d){rate.group(1)}\s*折"] if rate else []
    for word in KEYWORDS[kind]:
        for m in re.finditer(re.escape(word), text):
            window = text[max(0, m.start() - 80): m.end() + 80]
            if any(re.search(p, window) for p in patterns):
                return window.strip()
    return None


def main():
    def rows(name):
        with (CLEAN / name).open(encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    opentix = {(r["EventKey"], r["DiscountTypeName"]) for r in rows("opentix_discounts.csv")}
    todo = [r for r in rows("moc_discounts.csv") if (r["EventKey"], r["DiscountTypeName"]) not in opentix]
    results = []
    for r in todo:
        url = r["SourceURL"].strip()
        if not url:
            status, evidence = "沒有官網網址", ""
        else:
            text = page_text(url)
            if text is None:
                status, evidence = "無法讀取官網", ""
            else:
                args = (r["DiscountTypeName"], int(r["DiscountPrice"]), r["DiscountDescription"])
                evidence, where = find_evidence(text, *args) or "", url
                for link in [] if evidence else _links.get(url, []):  # 再看同網站的票價頁
                    linked = page_text(link)
                    if linked and (evidence := find_evidence(linked, *args) or ""):
                        where = link
                        break
                status = "官網核對通過" if evidence else "官網未找到"
                if evidence and where != url:
                    evidence = f"（{where}）{evidence}"
        results.append({**{k: r[k] for k in ("EventKey", "EventTitle", "DiscountTypeName", "DiscountPrice",
                                              "DiscountDescription", "SourceURL")},
                        "Status": status, "Evidence": evidence[:200]})
        print(f"{status}｜{r['DiscountTypeName']} {r['DiscountPrice']}｜{r['EventTitle'][:24]}", flush=True)
    REVIEW.mkdir(parents=True, exist_ok=True)
    with (REVIEW / "discount_verification.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]) if results else ["Status"])
        writer.writeheader()
        writer.writerows(results)
    counts = {}
    for r in results:
        counts[r["Status"]] = counts.get(r["Status"], 0) + 1
    print("合計：", counts)


if __name__ == "__main__":
    main()
