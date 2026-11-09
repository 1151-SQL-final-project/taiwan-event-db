"""產生測試用的 Access 資料庫 test_events.accdb。

用法（在專案根目錄）：
    .venv\\Scripts\\python db\\build_test_db.py

- 資料表結構見 schema.py；這裡只放少量「測試資料」。
- 活動日期以執行當天為基準往前後推算，所以隨時重建都會有
  「進行中／即將開始／已結束」的活動可以測。
- 三種角色各有一個測試帳號，活動也涵蓋四種審核狀態（待審核、上架中、已退回、已下架）。
- 真實資料（文化部開放資料＋人工建檔）請用 build_db.py。
"""
import datetime as dt
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "db"))
from security import hash_password  # noqa: E402
from schema import create_database, insert_rows  # noqa: E402

DB_PATH = pathlib.Path(__file__).resolve().parent / "test_events.accdb"

# ---- 測試資料 ----
# 假帳號，密碼都是 test1234。管理員帳號不開放註冊，由這裡建立
USERS = [  # (暱稱或商家名稱, 信箱, 角色)
    ("測試管理員", "admin@example.com", "管理員"),
    ("測試商家", "merchant@example.com", "商家"),
    ("測試同學", "student@example.com", "使用者"),
]
VENUES = [  # (名稱, 縣市, 地址)
    ("國立臺灣師範大學 圖書館校區", "臺北市", "臺北市大安區和平東路一段162號"),
    ("華山1914文化創意產業園區", "臺北市", "臺北市中正區八德路一段1號"),
    ("國立自然科學博物館", "臺中市", "臺中市北區館前路1號"),
    ("衛武營國家藝術文化中心", "高雄市", "高雄市鳳山區三多一路1號"),
    ("國立臺灣史前文化博物館", "臺東縣", "臺東縣臺東市博物館路1號"),
]
# (標題, 類別, 場館, 開始距今天數, 結束距今天數, 原價, 上架者信箱, 審核狀態, 描述)
EVENTS = [
    ("（測試）城市光影攝影展", "展覽", "華山1914文化創意產業園區", -10, 40, 250,
     "merchant@example.com", "上架中", "測試用展覽活動。"),
    ("（測試）AI 與資料素養講座", "講座", "國立臺灣師範大學 圖書館校區", 5, 5, 0,
     "merchant@example.com", "上架中", "測試用免費講座，需事先報名。"),
    ("（測試）手作皮革工作坊", "工作坊", "華山1914文化創意產業園區", 12, 12, 1200,
     "merchant@example.com", "上架中", "測試用工作坊。"),
    ("（測試）恐龍化石科普特展", "科普展覽", "國立自然科學博物館", -30, 60, 350,
     "admin@example.com", "上架中", "測試用科普展覽（模擬開放資料匯入，掛在管理員帳號下），有學生與早鳥優惠。"),
    ("（測試）寒假天文研習營", "研習營隊", "國立臺灣史前文化博物館", 80, 83, 3500,
     "merchant@example.com", "上架中", "測試用營隊，早鳥優惠即將截止。"),
    ("（測試）管弦樂巡迴音樂會", "音樂表演", "衛武營國家藝術文化中心", 20, 20, 500,
     "merchant@example.com", "上架中", "測試用音樂會，有學生票與早鳥票。"),
    ("（測試）週末文創市集", "市集", "華山1914文化創意產業園區", -2, 0, 0,
     "merchant@example.com", "上架中", "測試用市集，今天結束。"),
    ("（測試）已結束的舊展覽", "展覽", "國立臺灣史前文化博物館", -90, -5, 200,
     "admin@example.com", "上架中", "測試用：已結束但狀態還是上架中，啟動伺服器時會被自動下架。"),
    ("（測試）票價未公布的戲劇", "戲劇", "衛武營國家藝術文化中心", 45, 47, None,
     "merchant@example.com", "上架中", "測試用：票價未公布（空值）。"),
    ("（測試）待審核的親子科學營", "研習營隊", "國立自然科學博物館", 30, 32, 1800,
     "merchant@example.com", "待審核", "測試用：商家剛上架，等管理員審核。"),
    ("（測試）城市光影 攝影展 2026", "展覽", "華山1914文化創意產業園區", -3, 40, 250,
     "merchant@example.com", "待審核", "測試用：和已上架的「城市光影攝影展」幾乎一樣（重複上架），審核時會提醒管理員。"),
    ("（測試）被退回的講座", "講座", "國立臺灣師範大學 圖書館校區", 15, 15, 100,
     "merchant@example.com", "已退回", "測試用：資料不完整，被管理員退回。"),
    ("（測試）違規下架的市集", "市集", "華山1914文化創意產業園區", 3, 4, 0,
     "merchant@example.com", "已下架", "測試用：活動取消，被管理員下架。"),
    ("（測試）年度巨星巡迴演唱會", "音樂表演", "衛武營國家藝術文化中心", 45, 46, 2800,
     "merchant@example.com", "上架中", "測試用：熱門演唱會，還沒開賣（開賣後很快就會賣完）。"),
    ("（測試）跨年搖滾音樂祭", "音樂表演", "華山1914文化創意產業園區", 60, 61, 1800,
     "merchant@example.com", "上架中", "測試用：還沒開賣，開賣時間在十天後。"),
    ("（測試）已開賣的獨立樂團專場", "音樂表演", "華山1914文化創意產業園區", 25, 25, 900,
     "merchant@example.com", "上架中", "測試用：已經開賣。"),
]
# 開賣時間：(活動標題, 距今天數, 時間)
SALE_STARTS = [
    ("（測試）年度巨星巡迴演唱會", 2, "12:00"),
    ("（測試）跨年搖滾音樂祭", 10, "11:00"),
    ("（測試）已開賣的獨立樂團專場", -7, "12:00"),
    ("（測試）管弦樂巡迴音樂會", -10, "10:00"),
]
REJECT_REASONS = {"（測試）被退回的講座": "活動資訊不完整（缺少講者或報名方式）；補充：請補上講者介紹與報名連結"}
# (活動標題, 優惠類型, 說明, 特價, 開始距今天數或 None, 截止距今天數或 None)
DISCOUNTS = [
    ("（測試）城市光影攝影展", "學生優惠", "憑學生證購票", 150, None, None),
    ("（測試）恐龍化石科普特展", "學生優惠", "憑學生證購買優待票", 250, None, None),
    ("（測試）恐龍化石科普特展", "早鳥優惠", "早鳥預售（已截止）", 280, -60, -31),
    ("（測試）寒假天文研習營", "早鳥優惠", "早鳥報名優惠", 2800, -20, 3),
    ("（測試）寒假天文研習營", "學生優惠", "學生報名優惠", 3000, None, None),
    ("（測試）管弦樂巡迴音樂會", "學生優惠", "學生票（最低票區）", 250, None, None),
    ("（測試）管弦樂巡迴音樂會", "敬老優惠", "65 歲以上敬老票", 250, None, None),
    ("（測試）管弦樂巡迴音樂會", "早鳥優惠", "早鳥 85 折", 425, -10, 10),
    ("（測試）手作皮革工作坊", "團體優惠", "三人同行每人", 1000, None, None),
    ("（測試）待審核的親子科學營", "學生優惠", "國高中生報名優惠", 1500, None, None),
]
SAVES = [("student@example.com", "（測試）恐龍化石科普特展"), ("student@example.com", "（測試）寒假天文研習營"),
         ("student@example.com", "（測試）年度巨星巡迴演唱會")]


def at(days, hhmm="00:00"):
    hour, minute = map(int, hhmm.split(":"))
    day = dt.date.today() + dt.timedelta(days=days)
    return dt.datetime(day.year, day.month, day.day, hour, minute)


def add_users(db, ids, users=USERS):
    """建立帳號（密碼都是 test1234），回傳 {信箱: 使用者編號}。"""
    password_hash = hash_password("test1234")
    return insert_rows(db, "UserTable", [
        {"UserEmail": email, "UserName": name, "UserPasswordHash": password_hash, "UserRole": role}
        for name, email, role in users
    ])


def seed(db, ids, user_ids=None):
    """塞入測試場館、活動、優惠。user_ids 沒給時另外建測試帳號與收藏；
    build_db.py 會傳入已經建好的帳號（{信箱: 編號}），這裡就不再建帳號與收藏。"""
    city_ids, cat_ids, type_ids = ids["city"], ids["category"], ids["discount_type"]
    with_users = user_ids is None
    if with_users:
        user_ids = add_users(db, ids)
    sale = {title: at(days, hhmm) for title, days, hhmm in SALE_STARTS}
    venue_ids = insert_rows(db, "VenueTable", [
        {"VenueName": n, "VenueCity_FK": city_ids[c], "VenueAddress": a} for n, c, a in VENUES
    ])
    event_ids = insert_rows(db, "EventTable", [
        {
            "EventTitle": title, "EventCategory_FK": cat_ids[cat], "EventVenue_FK": venue_ids[venue],
            "EventStartDate": at(start), "EventEndDate": at(end), "EventOriginalPrice": price,
            "EventURL": "https://example.com/events", "EventDataSource": "測試資料",
            "EventOrganizer_FK": user_ids[organizer], "EventStatus": status, "EventDescription": desc,
            "EventSaleStartDate": sale.get(title), "EventRejectReason": REJECT_REASONS.get(title),
        }
        for title, cat, venue, start, end, price, organizer, status, desc in EVENTS
    ])
    insert_rows(db, "DiscountTable", [
        {
            "DiscountEvent_FK": event_ids[title], "DiscountType_FK": type_ids[kind],
            "DiscountDescription": desc, "DiscountPrice": price,
            "DiscountStartDate": at(s) if s is not None else None,
            "DiscountEndDate": at(e) if e is not None else None,
        }
        for title, kind, desc, price, s, e in DISCOUNTS
    ])
    if with_users:
        insert_rows(db, "SaveTable", [
            {"SaveUser_FK": user_ids[email], "SaveEvent_FK": event_ids[title]} for email, title in SAVES
        ])
    return event_ids


def main():
    db, ids = create_database(DB_PATH)
    try:
        seed(db, ids)
    finally:
        db.Close()
    print(f"已建立 {DB_PATH}")


if __name__ == "__main__":
    main()
