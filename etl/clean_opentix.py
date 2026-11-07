"""ETL 補充資料（Transform）：從 OPENTIX 活動頁整理出票價與優惠。

用法（在專案根目錄，先跑過 etl\\fetch_opentix.py）：
    .venv\\Scripts\\python etl\\clean_opentix.py

輸出：
    data/clean/opentix_prices.csv      活動原價（各票區全票的最低價）、票價區間、開賣時間
    data/clean/opentix_discounts.csv   學生、早鳥、敬老、團體優惠（格式同 moc_discounts.csv）
    data/review/opentix_report.md      統計

規則：
- 原價 = 各票區定價（全票）中的最低價；全部是 0 元 = 免費。
- 只收「一般人都能用」的優惠票種；名稱有 會員、卡、之友、代碼、信用、銀行 的（要先入會、持卡或有代碼）不收。
- 學生優惠優先用一般的學生票（學生票、在學學生票…）；沒有才用限定學校或校園推廣方案。
- 早鳥優惠一定要有截止時間（OPENTIX 票種的販售結束時間）。
- 優惠價必須低於同票區的全票價，也必須低於活動原價（最便宜票區可能沒有該優惠）；同一類優惠取最低價。
"""
import collections
import csv
import datetime as dt
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
from opentix_parse import parse_page  # noqa: E402

RAW_DIR = ROOT / "data" / "raw" / "opentix"
CLEAN_DIR = ROOT / "data" / "clean"
REVIEW_DIR = ROOT / "data" / "review"
URL_RE = re.compile(r"https://www\.opentix\.life/(?:program|event)/(\d+)")

EXCLUDE_WORDS = ["會員", "卡", "之友", "代碼", "信用", "銀行"]
GENERAL_STUDENT = re.compile(r"^(在學)?(大)?學生(票|優惠|證優惠|體驗票|優惠方案)?([，,、／/ ]?\d*折?優惠?)?$|^學生／青年優惠$")
RULES = [  # (優惠類型, 名稱判斷)
    ("早鳥優惠", lambda n: "早鳥" in n and "團體" not in n),
    ("學生優惠", lambda n: "學生" in n or "校園" in n),
    ("敬老優惠", lambda n: any(w in n for w in ("敬老", "長者", "65歲"))),
    ("團體優惠", lambda n: "團體" in n),
]
stats = collections.Counter()


def fit(text: str, limit: int) -> str:
    while len(text.encode("utf-16-le")) // 2 > limit:
        text = text[:-1]
    return text


def describe(plan: dict) -> str:
    rate = plan["rate"]
    rate_text = f"（{rate:g}折）" if isinstance(rate, (int, float)) and 0 < rate < 10 else ""
    text = f"OPENTIX 票種「{plan['name']}」{rate_text}"
    if plan["details"]:
        text += "：" + re.sub(r"\s+", " ", plan["details"])
    return fit(text, 100)


def pick_discounts(page: dict) -> list[dict]:
    """回傳這個活動每一類優惠中最便宜的一筆。"""
    candidates = collections.defaultdict(list)  # 類型 → [(價格, 是否一般學生票, plan)]
    for section in page["sections"]:
        full = section["price"]
        for plan in section["plans"]:
            name, price = plan["name"], plan["price"]
            if not isinstance(price, (int, float)) or not isinstance(full, (int, float)) or not (0 <= price < full):
                continue
            if any(w in name for w in EXCLUDE_WORDS):
                continue
            for kind, match in RULES:
                if match(name):
                    if kind == "早鳥優惠" and plan["end"] is None:
                        continue
                    general = kind != "學生優惠" or bool(GENERAL_STUDENT.match(re.sub(r"\s", "", name)))
                    candidates[kind].append((not general, price, plan))
                    break  # 一個票種只算一類（例如「早鳥學生票」算早鳥）
    picked = []
    for kind, items in candidates.items():
        _specific, price, plan = min(items, key=lambda x: (x[0], x[1]))  # 先挑一般票種，再挑最便宜
        picked.append({
            "DiscountTypeName": kind, "DiscountDescription": describe(plan), "DiscountPrice": int(price),
            "DiscountStartDate": plan["start"].strftime("%Y/%m/%d %H:%M") if kind == "早鳥優惠" and plan["start"] else "",
            "DiscountEndDate": plan["end"].strftime("%Y/%m/%d %H:%M") if kind == "早鳥優惠" else "",
        })
    return picked


def write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    with (CLEAN_DIR / "moc_events.csv").open(encoding="utf-8-sig") as f:
        # 同一場活動在多個場館時有多列（EventKey 相同），只取一次
        rows = {row["EventKey"]: row for row in csv.DictReader(f)}.values()
        events = [(m.group(1), row) for row in rows if (m := URL_RE.search(row["EventURL"]))]
    prices, discounts = [], []
    today = dt.date.today().strftime("%Y/%m/%d")
    for opentix_id, event in events:
        path = RAW_DIR / f"{opentix_id}.html.gz"
        if not path.exists():
            stats["頁面未下載"] += 1
            continue
        page = parse_page(path)
        url = f"https://www.opentix.life/event/{opentix_id}"
        full_prices = [s["price"] for s in page["sections"] if isinstance(s["price"], (int, float))]
        low, high = (min(full_prices), max(full_prices)) if full_prices else (page["low"], page["high"])
        if full_prices and low == 0 and high > 0:
            low = min(p for p in full_prices if p > 0)  # 有 0 元票區（例如工作人員席）時忽略
        if low is None:
            stats["頁面沒有票價"] += 1
            continue
        stats["取得票價"] += 1
        note = "免費" if high == 0 else f"OPENTIX 票價 NT${low:,}" + (f"–{high:,}" if high != low else "")
        sale = page["sale_start"].strftime("%Y/%m/%d %H:%M") if page["sale_start"] else ""
        if sale:
            stats["取得開賣時間"] += 1
            if sale[:10] >= today:
                stats["開賣時間：還沒到（以執行當天為準）"] += 1
        # /default/ 是 OPENTIX 沒有上傳主視覺時的預設圖，當成沒有圖片（網頁改顯示類別插圖）
        image = page["image"] if page["image"] and len(page["image"]) <= 255 and "/default/" not in page["image"] else ""
        if image:
            stats["取得活動圖片"] += 1
        prices.append({"EventKey": event["EventKey"], "EventOriginalPrice": int(low), "EventPriceNote": note,
                       "EventSaleStartDate": sale, "SourceURL": url,
                       "EventImageURL": image})
        for d in pick_discounts(page):
            # 票價依票區不同：最便宜的票區可能沒有學生票，學生票最低價反而比原價（最低全票）高，這種不收
            if d["DiscountPrice"] >= low:
                stats["優惠：不低於活動原價（票區不同），捨棄"] += 1
                continue
            stats[f"優惠：{d['DiscountTypeName']}"] += 1
            if d["DiscountTypeName"] == "早鳥優惠" and d["DiscountEndDate"][:10] < today:
                stats["優惠：早鳥（已截止，仍記錄）"] += 1
            discounts.append({"EventKey": event["EventKey"], "EventTitle": event["EventTitle"], **d,
                              "SourceURL": url, "RecordedBy": "OPENTIX 票種資料", "RecordedDate": today})

    write_csv(CLEAN_DIR / "opentix_prices.csv", prices,
              ["EventKey", "EventOriginalPrice", "EventPriceNote", "EventSaleStartDate", "SourceURL", "EventImageURL"])
    write_csv(CLEAN_DIR / "opentix_discounts.csv", discounts,
              ["EventKey", "EventTitle", "DiscountTypeName", "DiscountDescription", "DiscountPrice",
               "DiscountStartDate", "DiscountEndDate", "SourceURL", "RecordedBy", "RecordedDate"])
    lines = ["# OPENTIX 補充資料報告", "", f"- 對應到 OPENTIX 的活動：{len(events)} 筆", "",
             "| 項目 | 筆數 |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(stats.items())]
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (REVIEW_DIR / "opentix_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
