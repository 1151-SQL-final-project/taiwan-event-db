"""匯出 Google Sheet Query 用的資料：把多張資料表 JOIN 成一張「活動」大表。

用法（在專案根目錄，先跑過 db\\build_db.py）：
    .venv\\Scripts\\python etl\\export_sheets.py

輸出 data/sheets/events_flat.csv，上傳到 Google 試算表的「活動」工作表後，
就能用 docs/google-sheet-query.md 裡的 QUERY 公式查詢。

Google 試算表沒有 JOIN，所以這裡先把類別、場館、縣市、地區、優惠、收藏數都攤平成同一列
（反正規化）。只匯出上架中、還沒結束的活動（和網頁搜尋一樣）。
"""
import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
import db  # noqa: E402

OUT = ROOT / "data" / "sheets" / "events_flat.csv"
COLUMNS = ["活動編號", "活動名稱", "類別", "開始日期", "結束日期", "原價", "目前最低優惠價",
           "學生優惠", "早鳥優惠", "縣市", "地區", "場館", "類別分組", "收藏數"]


def main():
    with db.connect() as conn:
        events = db.query(conn, """
            SELECT e.EventID, e.EventTitle, c.CategoryName, c.CategoryGroup, e.EventStartDate, e.EventEndDate,
                   e.EventOriginalPrice, v.VenueName, ci.CityName, ci.CityRegion,
                   (SELECT COUNT(*) FROM SaveTable AS sv WHERE sv.SaveEvent_FK = e.EventID) AS SaveCount
            FROM ((EventTable AS e INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
            INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
            INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
            WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
            ORDER BY e.EventStartDate, e.EventID""")
        discounts = db.query(conn, """
            SELECT d.DiscountEvent_FK, t.DiscountTypeName, d.DiscountPrice
            FROM DiscountTable AS d INNER JOIN DiscountTypeTable AS t ON d.DiscountType_FK = t.DiscountTypeID
            WHERE (d.DiscountStartDate IS NULL OR d.DiscountStartDate <= Date())
              AND (d.DiscountEndDate IS NULL OR d.DiscountEndDate >= Date())""")

    best, kinds = {}, {}
    for d in discounts:
        eid = d["DiscountEvent_FK"]
        best[eid] = min(best.get(eid, d["DiscountPrice"]), d["DiscountPrice"])
        kinds.setdefault(eid, set()).add(d["DiscountTypeName"])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for e in events:
            eid = e["EventID"]
            writer.writerow([
                eid, e["EventTitle"], e["CategoryName"],
                e["EventStartDate"].strftime("%Y-%m-%d"), e["EventEndDate"].strftime("%Y-%m-%d"),
                "" if e["EventOriginalPrice"] is None else e["EventOriginalPrice"], best.get(eid, ""),
                "是" if "學生優惠" in kinds.get(eid, ()) else "否", "是" if "早鳥優惠" in kinds.get(eid, ()) else "否",
                e["CityName"], e["CityRegion"], e["VenueName"], e["CategoryGroup"], e["SaveCount"],
            ])
    print(f"已匯出 {len(events)} 筆活動到 {OUT}")


if __name__ == "__main__":
    main()
