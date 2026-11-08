"""示範活動：由示範商家上架的活動，讓 Demo 時各種情境都有資料
（即將開賣、早鳥即將截止、待審核、重複上架、已退回、已下架、票價未公布）。

build_db.py 預設會加入（加 --with-test-events 時改用 build_test_db.py 的測試活動）。
日期以建立資料庫當天為基準往前後推算，隨時重建都有即將開賣、早鳥即將截止的活動。
場館盡量用開放資料裡已有的場館，找不到才新增。
"""
from build_test_db import at
from schema import insert_rows

MERCHANT, ADMIN = "merchant@example.com", "admin@example.com"
NEW_VENUES = {  # 開放資料沒有的場館：名稱 → (縣市, 地址)
    "國立臺灣師範大學 綜合大樓國際會議廳": ("臺北市", "臺北市大安區和平東路一段162號"),
}
# (標題, 類別, 場館, 開始距今天數, 結束距今天數, 原價, 上架者信箱, 審核狀態, 說明)
EVENTS = [
    ("光影之間－城市街拍攝影聯展", "展覽", "華山1914文化創意產業園區 華山中3館2F 拱廳", -10, 40, 250, MERCHANT, "上架中",
     "集結十二位街頭攝影師的作品，從騎樓、夜市到捷運站，記錄城市裡稍縱即逝的光影。"),
    ("生成式 AI 與資料素養講座", "講座", "國立臺灣師範大學 綜合大樓國際會議廳", 5, 5, 0, MERCHANT, "上架中",
     "從日常使用 AI 工具的經驗出發，談如何判讀資料來源、避免被錯誤資訊誤導。免費入場，需事先報名。"),
    ("植鞣皮革小物手作工作坊", "工作坊", "華山1914文創園區東3B館 烏梅劇院", 12, 12, 1200, MERCHANT, "上架中",
     "兩小時完成一個植鞣皮革卡夾，材料與工具皆由現場提供，三人同行享優惠。"),
    ("遠古巨獸－恐龍化石特展", "科普展覽", "國立自然科學博物館", -30, 60, 350, ADMIN, "上架中",
     "展出暴龍、三角龍等化石骨架與復原模型，搭配互動投影介紹恐龍的演化與滅絕。"),
    ("星空下的天文研習營", "研習營隊", "國立臺灣史前文化博物館南科考古館", 80, 83, 3500, MERCHANT, "上架中",
     "四天三夜的寒假營隊，白天認識望遠鏡與星圖，晚上實地觀測冬季星空。早鳥報名即將截止。"),
    ("冬日序曲－管弦樂音樂會", "音樂表演", "衛武營國家藝術文化中心音樂廳", 20, 20, 500, MERCHANT, "上架中",
     "演出柴可夫斯基〈胡桃鉗〉組曲與德弗札克〈新世界〉交響曲，提供學生票與早鳥票。"),
    ("週末手作文創市集", "市集", "松山文創園區", -2, 0, 0, MERCHANT, "上架中",
     "三十個手作品牌與在地小農進駐，現場有插畫、陶藝與香氛體驗攤位。"),
    ("秋季版畫邀請展", "展覽", "國立自然科學博物館", -90, -5, 200, ADMIN, "上架中",
     "邀請十位版畫家以「季節」為題創作，展出木刻、絹印與銅版作品。"),
    ("《雨季》舞台劇", "戲劇", "衛武營國家藝術文化中心戲劇院", 45, 47, None, MERCHANT, "上架中",
     "一家人在梅雨季的老房子裡重新面對彼此的故事。票價將於近期公布。"),
    ("親子科學探索營", "研習營隊", "國立自然科學博物館", 30, 32, 1800, MERCHANT, "待審核",
     "三天的親子營隊，帶孩子動手做簡易電路、觀察微生物。"),
    ("光影之間 城市街拍攝影聯展 2026", "展覽", "華山1914文化創意產業園區 華山中3館2F 拱廳", -3, 40, 250, MERCHANT, "待審核",
     "集結十二位街頭攝影師的作品，記錄城市裡的光影。"),
    ("資料視覺化入門講座", "講座", "國立臺灣師範大學 綜合大樓國際會議廳", 15, 15, 100, MERCHANT, "已退回",
     "介紹常見圖表與配色原則。"),
    ("河畔二手書市集", "市集", "松山文創園區", 3, 4, 0, MERCHANT, "已下架",
     "因場地整修取消。"),
    ("Starlight 巡迴演唱會 高雄站", "音樂表演", "衛武營國家藝術文化中心表演廳", 45, 46, 2800, MERCHANT, "上架中",
     "人氣歌手睽違三年的巡迴演唱會，預計開賣後很快售完。"),
    ("跨年搖滾音樂祭", "音樂表演", "華山1914文創園區東3B館 烏梅劇院", 58, 59, 1800, MERCHANT, "上架中",
     "五組樂團接力演出，陪你一起倒數跨年。"),
    ("微光樂團 冬季專場", "音樂表演", "華山1914文創園區東3B館 烏梅劇院", 25, 25, 900, MERCHANT, "上架中",
     "獨立樂團微光的年度專場，演出全新專輯曲目。"),
]
SALE_STARTS = [  # (活動標題, 距今天數, 時間)
    ("Starlight 巡迴演唱會 高雄站", 2, "12:00"),
    ("跨年搖滾音樂祭", 10, "11:00"),
    ("微光樂團 冬季專場", -7, "12:00"),
    ("冬日序曲－管弦樂音樂會", -10, "10:00"),
]
REJECT_REASONS = {"資料視覺化入門講座": "活動資訊不完整（缺少講者或報名方式）；補充：請補上講者介紹與報名連結"}
DISCOUNTS = [  # (活動標題, 優惠類型, 說明, 特價, 開始距今天數或 None, 截止距今天數或 None)
    ("光影之間－城市街拍攝影聯展", "學生優惠", "憑學生證購票", 150, None, None),
    ("遠古巨獸－恐龍化石特展", "學生優惠", "憑學生證購買優待票", 250, None, None),
    ("遠古巨獸－恐龍化石特展", "早鳥優惠", "早鳥預售（已截止）", 280, -60, -31),
    ("星空下的天文研習營", "早鳥優惠", "早鳥報名優惠", 2800, -20, 3),
    ("星空下的天文研習營", "學生優惠", "學生報名優惠", 3000, None, None),
    ("冬日序曲－管弦樂音樂會", "學生優惠", "學生票（最低票區）", 250, None, None),
    ("冬日序曲－管弦樂音樂會", "敬老優惠", "65 歲以上敬老票", 250, None, None),
    ("冬日序曲－管弦樂音樂會", "早鳥優惠", "早鳥 85 折", 425, -10, 10),
    ("植鞣皮革小物手作工作坊", "團體優惠", "三人同行每人", 1000, None, None),
    ("親子科學探索營", "學生優惠", "國高中生報名優惠", 1500, None, None),
]
# 示範同學收藏的活動，「我的收藏」才有早鳥截止與開賣提醒
STUDENT_SAVES = ["星空下的天文研習營", "冬日序曲－管弦樂音樂會", "Starlight 巡迴演唱會 高雄站", "遠古巨獸－恐龍化石特展"]


def venue_ids(db, ids):
    """示範活動用到的場館：開放資料已有的直接用，沒有的新增。回傳 {場館名稱: 編號}。"""
    names = {e[2] for e in EVENTS}
    found = {}
    rs = db.OpenRecordset("SELECT VenueID, VenueName FROM VenueTable")
    while not rs.EOF:
        if rs.Fields("VenueName").Value in names:
            found.setdefault(rs.Fields("VenueName").Value, rs.Fields("VenueID").Value)
        rs.MoveNext()
    rs.Close()
    missing = [n for n in names if n not in found]
    found.update(insert_rows(db, "VenueTable", [
        {"VenueName": n, "VenueCity_FK": ids["city"][NEW_VENUES[n][0]], "VenueAddress": NEW_VENUES[n][1]} for n in missing
    ]))
    return found


def seed(db, ids, user_ids):
    """加入示範活動、優惠，以及示範同學的收藏。"""
    venues = venue_ids(db, ids)
    sale = {title: at(days, hhmm) for title, days, hhmm in SALE_STARTS}
    event_ids = insert_rows(db, "EventTable", [
        {
            "EventTitle": title, "EventCategory_FK": ids["category"][cat], "EventVenue_FK": venues[venue],
            "EventStartDate": at(start), "EventEndDate": at(end), "EventOriginalPrice": price,
            "EventDataSource": "商家上架" if organizer == MERCHANT else "人工建檔", "EventOrganizer_FK": user_ids[organizer], "EventStatus": status,
            "EventDescription": desc, "EventSaleStartDate": sale.get(title), "EventRejectReason": REJECT_REASONS.get(title),
        }
        for title, cat, venue, start, end, price, organizer, status, desc in EVENTS
    ])
    insert_rows(db, "DiscountTable", [
        {
            "DiscountEvent_FK": event_ids[title], "DiscountType_FK": ids["discount_type"][kind],
            "DiscountDescription": desc, "DiscountPrice": price,
            "DiscountStartDate": at(s) if s is not None else None,
            "DiscountEndDate": at(e) if e is not None else None,
        }
        for title, kind, desc, price, s, e in DISCOUNTS
    ])
    insert_rows(db, "SaveTable", [
        {"SaveUser_FK": user_ids["student@example.com"], "SaveEvent_FK": event_ids[title]} for title in STUDENT_SAVES
    ])
    return event_ids
