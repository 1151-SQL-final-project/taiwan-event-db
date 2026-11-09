"""ETL 第 3 步（Load）：把清理好的 CSV 匯入 Access，產生 events.accdb。

用法（在專案根目錄，先跑過 etl\\fetch_moc.py、etl\\clean_moc.py）：
    .venv\\Scripts\\python db\\build_db.py                     # 真實資料＋示範帳號與示範活動（正式的 events.accdb）
    .venv\\Scripts\\python db\\build_db.py --with-test-events --out db\\_test_source.accdb
                                                             # 自動測試用：再加上（測試）活動，另存一個檔案

匯入順序與來源（同一種資料，兩個來源都會匯入）：
    帳號   管理員、示範商家、示範使用者（假帳號，密碼都是 test1234）
    場館   data/clean/moc_venues.csv    + data/manual/venues.csv
    活動   data/clean/moc_events.csv    + data/manual/events.csv
    優惠   data/clean/opentix_discounts.csv + data/clean/moc_discounts.csv + data/manual/discounts.csv
    票價   data/clean/opentix_prices.csv 有資料時，覆蓋開放資料的票價（OPENTIX 的票價是結構化資料，比較準）
    開賣   data/clean/opentix_prices.csv 的開賣時間；人工建檔的活動在 events.csv 的 EventSaleStartDate 欄填

- 開放資料和人工建檔的活動沒有商家，EventOrganizer_FK 一律填管理員帳號，審核狀態直接是「上架中」。
- 同一場活動在多個場館舉辦時，CSV 有多列（EventKey 相同、場館不同），每列各是一筆活動，
  它的優惠會複製到每一筆。
- CSV 的 EventPriceNote（票價原始說明，例如「NT$800–2,200」）不是資料表欄位，加在活動說明開頭（【票價】…）。
- 同一場活動、同一類優惠，OPENTIX 有資料時就不用從開放資料文字自動擷取的那一筆。

CSV 裡的外鍵都寫名稱（縣市、類別、場館、優惠類型），這裡換成編號。
活動用 EventKey 對應；EventKey 空白時用 EventTitle。
有問題的資料列不會中斷匯入，會列在 data/review/load_errors.csv。
"""
import argparse
import csv
import datetime as dt
import pathlib
import random
import re
import sys

import pywintypes

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "db"))
from schema import com_value, create_database  # noqa: E402
import build_test_db  # noqa: E402
import demo_events  # noqa: E402
from security import hash_password  # noqa: E402

DB_PATH = ROOT / "db" / "events.accdb"
CLEAN, MANUAL, REVIEW = ROOT / "data" / "clean", ROOT / "data" / "manual", ROOT / "data" / "review"

errors: list[dict] = []


def read_csv(*paths: pathlib.Path) -> list[dict]:
    rows = []
    for path in paths:
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as f:
                rows += [dict(r, _source=f"{path.parent.name}/{path.name}:{i}") for i, r in enumerate(csv.DictReader(f), 2)]
    return rows


def parse_date(text: str | None):
    """接受 2026/10/12、2026-10-12、2026/10/12 19:30；空白回傳 None。"""
    text = (text or "").strip().replace("-", "/")
    if not text:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f"日期格式看不懂：{text}")


def parse_int(text: str | None):
    text = (text or "").strip().replace(",", "")
    return int(text) if text else None


def add_row(recordset, values: dict, source: str) -> int | None:
    """新增一筆資料，回傳自動編號；違反驗證規則或關聯時記錄錯誤、回傳 None。"""
    try:
        recordset.AddNew()
        for col, value in values.items():
            if value is not None and value != "":
                recordset.Fields(col).Value = com_value(value)
        new_id = recordset.Fields(0).Value  # 每張表第一個欄位都是自動編號主鍵
        recordset.Update()
        return new_id
    except pywintypes.com_error as exc:
        recordset.CancelUpdate()
        message = exc.excepinfo[2] if exc.excepinfo else str(exc)
        errors.append({"Source": source, "Error": message})
        return None


def lookup(mapping: dict, name: str, what: str, source: str):
    key = (name or "").strip()
    if key not in mapping:
        errors.append({"Source": source, "Error": f"找不到{what}「{key}」"})
        return None
    return mapping[key]


def load(db, ids, admin_id):
    """匯入場館、活動、優惠。回傳 {EventKey: [活動編號, ...]}（一場活動在多個場館時有多個編號）。"""
    venue_ids, event_ids = {}, {}

    rs = db.OpenRecordset("VenueTable", 2)
    for r in read_csv(CLEAN / "moc_venues.csv", MANUAL / "venues.csv"):
        if r["VenueName"].strip() in venue_ids:
            continue  # 人工建檔和開放資料有同一個場館
        city = lookup(ids["city"], r["CityName"], "縣市", r["_source"])
        if city is None:
            continue
        new_id = add_row(rs, {"VenueName": r["VenueName"].strip(), "VenueCity_FK": city,
                              "VenueAddress": r["VenueAddress"].strip()}, r["_source"])
        if new_id:
            venue_ids[r["VenueName"].strip()] = new_id
    rs.Close()

    opentix_prices = {r["EventKey"]: r for r in read_csv(CLEAN / "opentix_prices.csv")}
    rs = db.OpenRecordset("EventTable", 2)
    for r in read_csv(CLEAN / "moc_events.csv", MANUAL / "events.csv"):
        key = (r.get("EventKey") or "").strip() or r["EventTitle"].strip()
        if key in opentix_prices:
            r = {**r, "EventOriginalPrice": opentix_prices[key]["EventOriginalPrice"],
                 "EventPriceNote": opentix_prices[key]["EventPriceNote"],
                 "EventSaleStartDate": opentix_prices[key].get("EventSaleStartDate") or r.get("EventSaleStartDate"),
                 "EventImageURL": opentix_prices[key].get("EventImageURL") or r.get("EventImageURL")}
        category = lookup(ids["category"], r["CategoryName"], "類別", r["_source"])
        venue = lookup(venue_ids, r["VenueName"], "場館", r["_source"])
        if category is None or venue is None:
            continue
        note = (r.get("EventPriceNote") or "").strip()
        description = (r.get("EventDescription") or "").strip()
        if note:
            description = f"【票價】{note}" + (f"\n\n{description}" if description else "")
        try:
            values = {
                "EventCategory_FK": category, "EventVenue_FK": venue, "EventTitle": r["EventTitle"].strip(),
                "EventStartDate": parse_date(r["EventStartDate"]), "EventEndDate": parse_date(r["EventEndDate"]),
                "EventOriginalPrice": parse_int(r["EventOriginalPrice"]),
                "EventURL": (r.get("EventURL") or "").strip() or None,
                "EventDataSource": r["EventDataSource"].strip(),
                "EventOrganizer_FK": admin_id, "EventStatus": "上架中",
                "EventDescription": description or None,
                "EventSaleStartDate": parse_date(r.get("EventSaleStartDate")),
                "EventImageURL": (r.get("EventImageURL") or "").strip() or None,
                "EventShowTimes": (r.get("EventShowTimes") or "").strip() or None,
            }
        except ValueError as exc:
            errors.append({"Source": r["_source"], "Error": str(exc)})
            continue
        new_id = add_row(rs, values, r["_source"])
        if new_id:
            event_ids.setdefault(key, []).append(new_id)
    rs.Close()

    rs = db.OpenRecordset("DiscountTable", 2)
    opentix_rows = read_csv(CLEAN / "opentix_discounts.csv")
    from_opentix = {(r["EventKey"], r["DiscountTypeName"]) for r in opentix_rows}
    for r in opentix_rows + read_csv(CLEAN / "moc_discounts.csv", MANUAL / "discounts.csv"):
        key = (r.get("EventKey") or "").strip() or r["EventTitle"].strip()
        if r["_source"].startswith("clean/moc_discounts") and (key, r["DiscountTypeName"]) in from_opentix:
            continue  # OPENTIX 有同一類優惠的結構化資料，就不用文字擷取的版本
        events = lookup(event_ids, key, "活動", r["_source"])
        kind = lookup(ids["discount_type"], r["DiscountTypeName"], "優惠類型", r["_source"])
        if events is None or kind is None:
            continue
        try:
            values = {"DiscountType_FK": kind,
                      "DiscountDescription": r["DiscountDescription"].strip(),
                      "DiscountPrice": parse_int(r["DiscountPrice"]),
                      "DiscountStartDate": parse_date(r["DiscountStartDate"]),
                      "DiscountEndDate": parse_date(r["DiscountEndDate"])}
        except ValueError as exc:
            errors.append({"Source": r["_source"], "Error": str(exc)})
            continue
        for event in events:  # 一場活動在多個場館時，每一筆都有這個優惠
            add_row(rs, {"DiscountEvent_FK": event, **values}, r["_source"])
    rs.Close()
    return event_ids


# 示範帳號（全部是假帳號，密碼都是 test1234）。管理員帳號不開放註冊，由這裡建立
DEMO_USERS = [  # (暱稱或商家名稱, 信箱, 角色)
    ("示範管理員", "admin@example.com", "管理員"),
    ("示範商家", "merchant@example.com", "商家"),
    ("示範同學", "student@example.com", "使用者"),
]


def add_demo_users(db, ids):
    """建立示範帳號，另有 20 個示範使用者（demo01～demo20），之後隨機收藏活動，
    讓「熱門收藏排行」有資料。回傳 {信箱: 使用者編號}。"""
    users = DEMO_USERS + [(f"示範使用者{i:02d}", f"demo{i:02d}@example.com", "使用者") for i in range(1, 21)]
    return build_test_db.add_users(db, ids, users)


def add_demo_saves(db, user_ids, event_ids):
    rng = random.Random(115)
    # 熱門程度不平均：少數活動被很多人收藏，比較像真實情況
    events = [i for same_key in event_ids.values() for i in same_key]
    popular = rng.sample(events, min(15, len(events)))
    rs = db.OpenRecordset("SaveTable", 2)
    for email, user_id in user_ids.items():
        if not email.startswith("demo"):
            continue
        picks = set(rng.sample(popular, rng.randint(1, 6))) | set(rng.sample(events, rng.randint(0, 3)))
        for event_id in picks:
            add_row(rs, {"SaveUser_FK": user_id, "SaveEvent_FK": event_id,
                         "SaveDate": dt.datetime.now() - dt.timedelta(days=rng.randint(0, 30), minutes=rng.randint(0, 1440))},
                    "demo")
    rs.Close()


# sql/ 裡的查詢存進 Access 時用的名稱（Access 左側「查詢」清單看得到，表單精靈也能選）
QUERY_NAMES = {
    "search_events": "查_搜尋活動（基本）", "event_detail": "查_活動詳情",
    "event_discounts": "查_活動優惠", "list_categories": "查_類別清單", "list_cities": "查_縣市清單",
    "list_discount_types": "查_優惠類型清單", "list_venues": "查_場館清單", "list_saves": "查_我的收藏",
    "user_by_email": "查_用信箱找使用者", "user_by_id": "查_使用者資料",
    "stats_events_by_region": "統計_各地區活動數", "stats_events_by_city": "統計_各縣市活動數",
    "stats_events_by_category": "統計_各類別活動數", "popular_saves": "統計_熱門收藏排行",
    "early_bird_ending_soon": "提醒_早鳥即將截止", "save_reminders": "提醒_收藏優惠即將截止",
    "sale_starting_soon": "提醒_即將開賣", "save_sale_reminders": "提醒_收藏活動即將開賣",
    "insert_user": "新增_使用者", "update_user_name": "修改_使用者名稱", "insert_save": "新增_收藏", "delete_save": "刪除_收藏",
    "insert_venue": "新增_場館", "insert_discount": "新增_優惠",
    "merchant/list_my_events": "商家_我的活動", "merchant/insert_event": "商家_上架活動",
    "merchant/update_event": "商家_修改活動", "merchant/delete_event_discounts": "商家_清除活動優惠",
    "merchant/my_stats_by_status": "統計_我的活動成效",
    "merchant/venue_events_overlap": "商家_同場館同期間活動",
    "admin/list_events": "管理_所有活動", "admin/pending_events": "管理_待審核活動",
    "admin/update_event_status": "管理_修改審核狀態", "admin/similar_events": "管理_日期重疊的活動（查重複）", "admin/stats_events_by_status": "統計_各審核狀態活動數",
    "admin/organizer_history": "管理_上架者審核紀錄",
    "admin/count_ended_active": "管理_預覽待下架活動", "admin/deactivate_ended_events": "管理_一鍵下架已結束活動",
    "admin/reactivate_event": "管理_重新上架活動", "admin/insert_event": "管理_新增活動",
    "admin/update_event_price": "管理_修改票價", "admin/update_discount": "管理_修改優惠",
    "admin/delete_expired_discounts": "管理_刪除過期優惠", "admin/delete_event": "管理_刪除活動",
}
# [@參數] 在 Access 裡執行時跳出的提示文字
PARAM_PROMPTS = {
    "days": "幾天內", "user_id": "使用者編號", "event_id": "活動編號", "email": "信箱", "name": "名稱",
    "password_hash": "密碼雜湊值", "role": "角色（使用者或商家）",
    "new_end_date": "新的結束日期", "category_id": "類別編號", "title": "活動名稱", "start_date": "開始日期",
    "end_date": "結束日期", "price": "價格", "url": "網址", "data_source": "資料來源", "description": "說明",
    "venue_id": "場館編號", "city_id": "縣市編號", "address": "地址", "discount_type_id": "優惠類型編號",
    "discount_id": "優惠編號", "organizer_id": "上架商家編號", "status": "審核狀態（待審核、上架中、已退回、已下架）",
    "reason": "退回理由（不是退回請留空）", "sale_start": "開賣時間（yyyy/mm/dd hh:nn，沒有請留空）",
}


def add_saved_queries(db):
    """把 sql/*.sql 存成 Access 的「查詢」物件，參數 [@days] 換成 [請輸入 幾天內] 這種中文提示。"""
    for path in sorted((ROOT / "sql").rglob("*.sql")):
        key = path.relative_to(ROOT / "sql").with_suffix("").as_posix()
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if not ln.strip().startswith("--")]
        sql = re.sub(r"\[@(\w+)\]", lambda m: f"[請輸入 {PARAM_PROMPTS.get(m.group(1), m.group(1))}]", "\n".join(lines))
        try:
            db.CreateQueryDef(QUERY_NAMES.get(key, key.replace("/", "_")), sql.strip())
        except pywintypes.com_error as exc:
            errors.append({"Source": f"sql/{key}.sql", "Error": exc.excepinfo[2] if exc.excepinfo else str(exc)})


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-test-events", action="store_true",
                        help="加上 build_test_db.py 的（測試）活動（含待審核、已退回、已下架，自動測試用）")
    parser.add_argument("--out", type=pathlib.Path, default=DB_PATH, help="輸出的資料庫檔案（預設 db/events.accdb）")
    args = parser.parse_args()

    db, ids = create_database(args.out)
    try:
        user_ids = add_demo_users(db, ids)
        event_ids = load(db, ids, user_ids["admin@example.com"])
        if args.with_test_events:
            build_test_db.seed(db, ids, user_ids)
        else:
            demo_events.seed(db, ids, user_ids)  # 示範商家上架的活動（即將開賣、早鳥即將截止、待審核等情境）
        add_demo_saves(db, user_ids, event_ids)
        if args.with_test_events:
            # 讓示範同學收藏有早鳥優惠的測試活動，Demo「收藏提醒」時才有資料
            db.Execute(
                "INSERT INTO SaveTable (SaveUser_FK, SaveEvent_FK) "
                "SELECT u.UserID, e.EventID FROM UserTable AS u, EventTable AS e "
                "WHERE u.UserEmail = 'student@example.com' "
                "AND e.EventTitle IN ('（測試）寒假天文研習營', '（測試）管弦樂巡迴音樂會', '（測試）年度巨星巡迴演唱會')"
            )
        add_saved_queries(db)
        counts = {}
        for table in ["VenueTable", "EventTable", "DiscountTable", "UserTable", "SaveTable"]:
            rs = db.OpenRecordset(f"SELECT COUNT(*) FROM {table}")  # 先存成變數，COM 物件才不會被提早釋放
            counts[table] = rs.Fields(0).Value
            rs.Close()
    finally:
        db.Close()

    REVIEW.mkdir(parents=True, exist_ok=True)
    with (REVIEW / "load_errors.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Source", "Error"])
        writer.writeheader()
        writer.writerows(errors)
    print(f"已建立 {args.out}")
    for table, n in counts.items():
        print(f"  {table}: {n}")
    print(f"  匯入失敗：{len(errors)} 列（見 data/review/load_errors.csv）")


if __name__ == "__main__":
    main()
