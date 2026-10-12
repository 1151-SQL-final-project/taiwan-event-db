"""產生測試用的 Access 資料庫 test_events.accdb。

用法（在專案根目錄）：
    .venv\\Scripts\\python db\\build_test_db.py

- 資料表、欄位型態、驗證規則、預設值、查閱欄位、關聯都照
  HW1_TableSchemaSketch_41411016E_修改版.xlsx，再加上 docs/schema-v2.md 的修改
  （SessionTable 場次表、EventPriceNote、EventOriginalPrice 允許空值）。
- 塞入少量「測試資料」，活動日期以執行當天為基準往前後推算，
  所以隨時重建都會有「進行中／即將開始／已結束」的活動可以測。
- 這只是測試檔。正式的 Access 主檔由晏均維護，不要把這個檔案當主檔。

技術說明：透過 DAO（Access 內建的資料庫引擎介面）建表，因為驗證規則、
預設值、查閱欄位這些設定，用 SQL 的 CREATE TABLE 做不到。
"""
import datetime as dt
import pathlib
import sys

import win32com.client

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))
from security import hash_password  # noqa: E402

DB_PATH = pathlib.Path(__file__).resolve().parent / "test_events.accdb"

# ---- DAO 常數 ----
DB_LANG_CHINESE_TRADITIONAL = ";LANGID=0x0404;CP=950;COUNTRY=0"
DB_VERSION_120 = 128          # .accdb 格式
DB_BOOLEAN, DB_LONG, DB_DATE, DB_TEXT, DB_MEMO, DB_INTEGER = 1, 4, 8, 10, 12, 3
DB_AUTO_INCR = 16
DB_HYPERLINK = 32768
DB_RELATION_DELETE_CASCADE = 4096
AC_CHECKBOX, AC_COMBOBOX = 106, 111

# ---- 資料表定義 ----
# 每個欄位：(名稱, 型態, 長度, 選項)
# 選項：caption 欄位標題、required 必填、default 預設值、rule/rule_text 欄位驗證規則、
#       format 格式、lookup=(資料表, 編號欄, 顯示欄) 查閱欄位、hyperlink 超連結
TABLES = {
    "CategoryTable": {
        "fields": [
            ("CategoryID", "auto", None, {"caption": "類別編號"}),
            ("CategoryName", DB_TEXT, 20, {"caption": "類別名稱", "required": True}),
        ],
        "unique": [["CategoryName"]],
    },
    "CityTable": {
        "fields": [
            ("CityID", "auto", None, {"caption": "縣市編號"}),
            ("CityName", DB_TEXT, 10, {"caption": "縣市名稱", "required": True}),
            ("CityRegion", DB_TEXT, 10, {
                "caption": "所屬地區", "required": True,
                "rule": 'In ("北部","中部","南部","東部","離島")',
                "rule_text": "所屬地區只能是 北部、中部、南部、東部、離島",
            }),
        ],
        "unique": [["CityName"]],
        "index": ["CityRegion"],
    },
    "VenueTable": {
        "fields": [
            ("VenueID", "auto", None, {"caption": "場館編號"}),
            ("VenueName", DB_TEXT, 50, {"caption": "場館名稱", "required": True}),
            ("VenueCity_FK", DB_LONG, None, {
                "caption": "場館所在縣市", "required": True,
                "lookup": ("CityTable", "CityID", "CityName"),
            }),
            ("VenueAddress", DB_TEXT, 100, {"caption": "場館完整地址", "required": True}),
        ],
        "index": ["VenueName", "VenueCity_FK"],
    },
    "EventTable": {
        "fields": [
            ("EventID", "auto", None, {"caption": "活動編號"}),
            ("EventCategory_FK", DB_LONG, None, {
                "caption": "活動所屬類別", "required": True,
                "lookup": ("CategoryTable", "CategoryID", "CategoryName"),
            }),
            ("EventTitle", DB_TEXT, 100, {"caption": "活動名稱", "required": True}),
            ("EventStartDate", DB_DATE, None, {"caption": "活動開始日期", "required": True, "format": "yyyy/mm/dd"}),
            ("EventEndDate", DB_DATE, None, {"caption": "活動結束日期", "required": True, "format": "yyyy/mm/dd"}),
            # 票價規則：存最低票價；0 = 免費；Null = 票價不明（見 docs/schema-v2.md）
            ("EventOriginalPrice", DB_LONG, None, {
                "caption": "活動原價（最低票價）",
                "rule": ">=0", "rule_text": "票價不能是負數（免費請填 0，不明請留空）",
            }),
            ("EventPriceNote", DB_TEXT, 100, {"caption": "票價原始說明"}),
            ("EventURL", DB_MEMO, None, {"caption": "活動官方網址", "hyperlink": True}),
            ("EventDataSource", DB_TEXT, 50, {"caption": "資料來源", "required": True}),
            ("EventIsActive", DB_BOOLEAN, None, {"caption": "是否上架", "default": "Yes"}),
            ("EventDescription", DB_MEMO, None, {"caption": "活動詳細說明"}),
        ],
        "table_rule": ("[EventEndDate]>=[EventStartDate]", "活動結束日期不能早於開始日期"),
        "index": ["EventCategory_FK", "EventTitle", "EventStartDate", "EventEndDate",
                  "EventOriginalPrice", "EventIsActive"],
    },
    # 新增：場次表。一場活動可以在多個場館、多個時間舉行（巡演、多場次）
    "SessionTable": {
        "fields": [
            ("SessionID", "auto", None, {"caption": "場次編號"}),
            ("SessionEvent_FK", DB_LONG, None, {
                "caption": "場次所屬活動", "required": True,
                "lookup": ("EventTable", "EventID", "EventTitle"),
            }),
            ("SessionVenue_FK", DB_LONG, None, {
                "caption": "場次舉辦場館", "required": True,
                "lookup": ("VenueTable", "VenueID", "VenueName"),
            }),
            ("SessionStartTime", DB_DATE, None, {"caption": "場次開始時間", "required": True, "format": "yyyy/mm/dd hh:nn"}),
            ("SessionEndTime", DB_DATE, None, {"caption": "場次結束時間", "format": "yyyy/mm/dd hh:nn"}),
        ],
        "table_rule": ("[SessionEndTime]>=[SessionStartTime] Or [SessionEndTime] Is Null",
                       "場次結束時間不能早於開始時間"),
        "index": ["SessionEvent_FK", "SessionVenue_FK", "SessionStartTime"],
    },
    "DiscountTypeTable": {
        "fields": [
            ("DiscountTypeID", "auto", None, {"caption": "優惠類型編號"}),
            ("DiscountTypeName", DB_TEXT, 20, {"caption": "優惠類型名稱", "required": True}),
        ],
        "unique": [["DiscountTypeName"]],
    },
    "DiscountTable": {
        "fields": [
            ("DiscountID", "auto", None, {"caption": "優惠紀錄編號"}),
            ("DiscountEvent_FK", DB_LONG, None, {
                "caption": "優惠對應活動", "required": True,
                "lookup": ("EventTable", "EventID", "EventTitle"),
            }),
            ("DiscountType_FK", DB_LONG, None, {
                "caption": "優惠類型", "required": True,
                "lookup": ("DiscountTypeTable", "DiscountTypeID", "DiscountTypeName"),
            }),
            ("DiscountDescription", DB_TEXT, 100, {"caption": "優惠詳細說明"}),
            ("DiscountPrice", DB_LONG, None, {
                "caption": "優惠特價金額", "required": True,
                "rule": ">=0", "rule_text": "優惠價不能是負數",
            }),
            # 開始日期空值 = 與活動期間相同；截止日期空值 = 沒有截止日（一直有效）
            ("DiscountStartDate", DB_DATE, None, {"caption": "優惠開始日期", "format": "yyyy/mm/dd"}),
            ("DiscountEndDate", DB_DATE, None, {"caption": "優惠截止日期", "format": "yyyy/mm/dd"}),
        ],
        "table_rule": ("[DiscountEndDate]>=[DiscountStartDate] Or [DiscountEndDate] Is Null Or [DiscountStartDate] Is Null",
                       "優惠截止日期不能早於開始日期"),
        "index": ["DiscountEvent_FK", "DiscountType_FK", "DiscountPrice", "DiscountStartDate", "DiscountEndDate"],
    },
    "UserTable": {
        "fields": [
            ("UserID", "auto", None, {"caption": "使用者編號"}),
            ("UserName", DB_TEXT, 20, {"caption": "使用者暱稱", "required": True}),
            ("UserEmail", DB_TEXT, 50, {
                "caption": "使用者登入信箱", "required": True,
                "rule": 'Like "*@*.*"', "rule_text": "請輸入正確的電子郵件格式",
            }),
            ("UserPasswordHash", DB_TEXT, 255, {"caption": "使用者密碼雜湊值", "required": True}),
            ("UserDefaultCity_FK", DB_LONG, None, {
                "caption": "使用者預設縣市",
                "lookup": ("CityTable", "CityID", "CityName"),
            }),
        ],
        "unique": [["UserEmail"]],
    },
    "SaveTable": {
        "fields": [
            ("SaveID", "auto", None, {"caption": "收藏紀錄編號"}),
            ("SaveUser_FK", DB_LONG, None, {
                "caption": "收藏者編號", "required": True,
                "lookup": ("UserTable", "UserID", "UserEmail"),
            }),
            ("SaveEvent_FK", DB_LONG, None, {
                "caption": "收藏活動編號", "required": True,
                "lookup": ("EventTable", "EventID", "EventTitle"),
            }),
            ("SaveDate", DB_DATE, None, {
                "caption": "收藏建立時間", "required": True,
                "default": "Now()", "format": "yyyy/mm/dd hh:nn",
            }),
        ],
        # 同一人不能重複收藏同一活動
        "unique": [["SaveUser_FK", "SaveEvent_FK"]],
        "index": ["SaveEvent_FK"],
    },
}

# (父表, 父鍵, 子表, 外鍵, 是否串聯刪除)
# 收藏、優惠、場次跟著活動走：刪除活動時一起刪掉；其他關聯不允許刪除還在使用中的資料
RELATIONS = [
    ("CityTable", "CityID", "VenueTable", "VenueCity_FK", False),
    ("CityTable", "CityID", "UserTable", "UserDefaultCity_FK", False),
    ("CategoryTable", "CategoryID", "EventTable", "EventCategory_FK", False),
    ("EventTable", "EventID", "SessionTable", "SessionEvent_FK", True),
    ("VenueTable", "VenueID", "SessionTable", "SessionVenue_FK", False),
    ("EventTable", "EventID", "DiscountTable", "DiscountEvent_FK", True),
    ("DiscountTypeTable", "DiscountTypeID", "DiscountTable", "DiscountType_FK", False),
    ("UserTable", "UserID", "SaveTable", "SaveUser_FK", True),
    ("EventTable", "EventID", "SaveTable", "SaveEvent_FK", True),
]


def add_property(obj, name, prop_type, value):
    obj.Properties.Append(obj.CreateProperty(name, prop_type, value))


def create_table(db, name, spec):
    td = db.CreateTableDef(name)
    pk_name = None
    for field_name, field_type, size, opts in spec["fields"]:
        if field_type == "auto":
            fld = td.CreateField(field_name, DB_LONG)
            fld.Attributes = fld.Attributes | DB_AUTO_INCR
            pk_name = field_name
        elif field_type == DB_TEXT:
            fld = td.CreateField(field_name, DB_TEXT, size)
        else:
            fld = td.CreateField(field_name, field_type)
        if opts.get("hyperlink"):
            fld.Attributes = fld.Attributes | DB_HYPERLINK
        fld.Required = bool(opts.get("required")) or field_type == "auto"
        if field_type in (DB_TEXT, DB_MEMO):
            fld.AllowZeroLength = False
        if "default" in opts:
            fld.DefaultValue = opts["default"]
        if "rule" in opts:
            fld.ValidationRule = opts["rule"]
            fld.ValidationText = opts["rule_text"]
        td.Fields.Append(fld)

    if "table_rule" in spec:
        td.ValidationRule, td.ValidationText = spec["table_rule"]

    idx = td.CreateIndex("PrimaryKey")
    idx.Primary = True
    idx.Unique = True
    idx.Fields.Append(idx.CreateField(pk_name))
    td.Indexes.Append(idx)
    for cols in spec.get("unique", []):
        idx = td.CreateIndex("UQ_" + "_".join(cols))
        idx.Unique = True
        for col in cols:
            idx.Fields.Append(idx.CreateField(col))
        td.Indexes.Append(idx)
    for col in spec.get("index", []):
        idx = td.CreateIndex("IX_" + col)
        idx.Fields.Append(idx.CreateField(col))
        td.Indexes.Append(idx)

    db.TableDefs.Append(td)

    # 欄位標題、格式、查閱欄位、核取方塊要在資料表建好之後才能設定
    for field_name, field_type, _size, opts in spec["fields"]:
        fld = db.TableDefs(name).Fields(field_name)
        add_property(fld, "Caption", DB_TEXT, opts["caption"])
        if "format" in opts:
            add_property(fld, "Format", DB_TEXT, opts["format"])
        if field_type == DB_BOOLEAN:
            add_property(fld, "DisplayControl", DB_INTEGER, AC_CHECKBOX)
        if "lookup" in opts:
            table, key, label = opts["lookup"]
            add_property(fld, "DisplayControl", DB_INTEGER, AC_COMBOBOX)
            add_property(fld, "RowSourceType", DB_TEXT, "Table/Query")
            add_property(fld, "RowSource", DB_TEXT, f"SELECT [{key}], [{label}] FROM [{table}] ORDER BY [{key}];")
            add_property(fld, "BoundColumn", DB_INTEGER, 1)
            add_property(fld, "ColumnCount", DB_INTEGER, 2)
            add_property(fld, "ColumnWidths", DB_TEXT, "0;2880")
            add_property(fld, "LimitToList", DB_BOOLEAN, True)


def create_relation(db, parent, parent_key, child, child_key, cascade):
    rel = db.CreateRelation(f"{parent}{child}_{child_key}", parent, child,
                            DB_RELATION_DELETE_CASCADE if cascade else 0)
    fld = rel.CreateField(parent_key)
    fld.ForeignName = child_key
    rel.Fields.Append(fld)
    db.Relations.Append(rel)


# ---- 測試資料 ----
CITIES = [
    ("臺北市", "北部"), ("新北市", "北部"), ("基隆市", "北部"), ("桃園市", "北部"),
    ("新竹市", "北部"), ("新竹縣", "北部"),
    ("苗栗縣", "中部"), ("臺中市", "中部"), ("彰化縣", "中部"), ("南投縣", "中部"), ("雲林縣", "中部"),
    ("嘉義市", "南部"), ("嘉義縣", "南部"), ("臺南市", "南部"), ("高雄市", "南部"), ("屏東縣", "南部"),
    ("宜蘭縣", "東部"), ("花蓮縣", "東部"), ("臺東縣", "東部"),
    ("澎湖縣", "離島"), ("金門縣", "離島"), ("連江縣", "離島"),
]
CATEGORIES = ["展覽", "講座", "工作坊", "科普展覽", "研習營隊", "音樂表演", "戲劇", "市集", "體育賽事"]
DISCOUNT_TYPES = ["學生優惠", "早鳥優惠", "敬老優惠", "團體優惠"]
VENUES = [  # (名稱, 縣市, 地址)
    ("國立臺灣師範大學 圖書館校區", "臺北市", "臺北市大安區和平東路一段162號"),
    ("華山1914文化創意產業園區", "臺北市", "臺北市中正區八德路一段1號"),
    ("國立自然科學博物館", "臺中市", "臺中市北區館前路1號"),
    ("衛武營國家藝術文化中心", "高雄市", "高雄市鳳山區三多一路1號"),
    ("國立臺灣史前文化博物館", "臺東縣", "臺東縣臺東市博物館路1號"),
]
# (標題, 類別, 開始距今天數, 結束距今天數, 原價, 票價說明, 描述)
EVENTS = [
    ("（測試）城市光影攝影展", "展覽", -10, 40, 250, None, "測試用展覽活動。"),
    ("（測試）AI 與資料素養講座", "講座", 5, 5, 0, "免費，需事先報名", "測試用免費講座。"),
    ("（測試）手作皮革工作坊", "工作坊", 12, 12, 1200, None, "測試用工作坊。"),
    ("（測試）恐龍化石科普特展", "科普展覽", -30, 60, 350, "全票 350／優待票 250", "測試用科普展覽，有學生與早鳥優惠。"),
    ("（測試）寒假天文研習營", "研習營隊", 80, 83, 3500, None, "測試用營隊，早鳥優惠即將截止。"),
    ("（測試）管弦樂巡迴音樂會", "音樂表演", 20, 34, 500, "500–2000（依座位區）", "測試用巡演活動：三個城市、三個場次。"),
    ("（測試）週末文創市集", "市集", -2, 0, 0, "免費入場", "測試用市集，今天結束。"),
    ("（測試）已結束的舊展覽", "展覽", -90, -5, 200, None, "測試用：已結束、應被下架的活動。"),
    ("（測試）票價未公布的戲劇", "戲劇", 45, 47, None, "票價將於售票時公布", "測試用：票價不明（空值）。"),
]
# (活動標題, 場館, 開始距今天數, 時:分, 結束距今天數或 None, 時:分)
SESSIONS = [
    ("（測試）城市光影攝影展", "華山1914文化創意產業園區", -10, "10:00", 40, "18:00"),
    ("（測試）AI 與資料素養講座", "國立臺灣師範大學 圖書館校區", 5, "14:00", 5, "16:00"),
    ("（測試）手作皮革工作坊", "華山1914文化創意產業園區", 12, "13:30", 12, "17:00"),
    ("（測試）恐龍化石科普特展", "國立自然科學博物館", -30, "09:00", 60, "17:00"),
    ("（測試）寒假天文研習營", "國立臺灣史前文化博物館", 80, "09:00", 83, "16:00"),
    ("（測試）管弦樂巡迴音樂會", "衛武營國家藝術文化中心", 20, "19:30", None, None),
    ("（測試）管弦樂巡迴音樂會", "國立自然科學博物館", 27, "19:30", None, None),
    ("（測試）管弦樂巡迴音樂會", "國立臺灣師範大學 圖書館校區", 34, "19:30", None, None),
    ("（測試）週末文創市集", "華山1914文化創意產業園區", -2, "11:00", 0, "20:00"),
    ("（測試）已結束的舊展覽", "國立臺灣史前文化博物館", -90, "09:00", -5, "17:00"),
    ("（測試）票價未公布的戲劇", "衛武營國家藝術文化中心", 45, "19:30", 47, "21:30"),
]
# (活動標題, 優惠類型, 說明, 特價, 開始距今天數或 None, 截止距今天數或 None)
DISCOUNTS = [
    ("（測試）城市光影攝影展", "學生優惠", "憑學生證購票", 150, None, None),
    ("（測試）恐龍化石科普特展", "學生優惠", "憑學生證購買優待票", 250, None, None),
    ("（測試）恐龍化石科普特展", "早鳥優惠", "早鳥預售（已截止）", 280, -60, -31),
    ("（測試）寒假天文研習營", "早鳥優惠", "早鳥報名優惠", 2800, -20, 3),
    ("（測試）寒假天文研習營", "學生優惠", "學生報名優惠", 3000, None, None),
    ("（測試）管弦樂巡迴音樂會", "學生優惠", "學生票（最低票區）", 250, None, None),
    ("（測試）管弦樂巡迴音樂會", "早鳥優惠", "早鳥 85 折", 425, -10, 10),
    ("（測試）手作皮革工作坊", "團體優惠", "三人同行每人", 1000, None, None),
]
# 假帳號，密碼都是 test1234
USERS = [("測試同學", "student@example.com", "臺北市"), ("測試管理員", "admin@example.com", "高雄市")]
SAVES = [("student@example.com", "（測試）恐龍化石科普特展"), ("student@example.com", "（測試）寒假天文研習營")]


def insert_rows(db, table, rows):
    """用 DAO Recordset 新增資料，回傳 {第一欄的值: 新的自動編號}。"""
    rs = db.OpenRecordset(table, 2)  # dbOpenDynaset
    pk = db.TableDefs(table).Indexes("PrimaryKey").Fields(0).Name
    ids = {}
    for row in rows:
        rs.AddNew()
        for col, value in row.items():
            if value is not None:
                rs.Fields(col).Value = value
        new_id = rs.Fields(pk).Value
        rs.Update()
        ids[next(iter(row.values()))] = new_id
    rs.Close()
    return ids


def at(days, hhmm="00:00"):
    hour, minute = map(int, hhmm.split(":"))
    day = dt.date.today() + dt.timedelta(days=days)
    return dt.datetime(day.year, day.month, day.day, hour, minute)


def seed(db):
    city_ids = insert_rows(db, "CityTable", [{"CityName": n, "CityRegion": r} for n, r in CITIES])
    cat_ids = insert_rows(db, "CategoryTable", [{"CategoryName": n} for n in CATEGORIES])
    type_ids = insert_rows(db, "DiscountTypeTable", [{"DiscountTypeName": n} for n in DISCOUNT_TYPES])
    venue_ids = insert_rows(db, "VenueTable", [
        {"VenueName": n, "VenueCity_FK": city_ids[c], "VenueAddress": a} for n, c, a in VENUES
    ])
    event_ids = insert_rows(db, "EventTable", [
        {
            "EventTitle": title, "EventCategory_FK": cat_ids[cat],
            "EventStartDate": at(start), "EventEndDate": at(end),
            "EventOriginalPrice": price, "EventPriceNote": note,
            "EventDataSource": "測試資料", "EventIsActive": True, "EventDescription": desc,
            "EventURL": "測試網址#https://example.com/events#",
        }
        for title, cat, start, end, price, note, desc in EVENTS
    ])
    insert_rows(db, "SessionTable", [
        {
            "SessionEvent_FK": event_ids[title], "SessionVenue_FK": venue_ids[venue],
            "SessionStartTime": at(sd, st), "SessionEndTime": at(ed, et) if ed is not None else None,
        }
        for title, venue, sd, st, ed, et in SESSIONS
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
    password_hash = hash_password("test1234")
    user_ids = insert_rows(db, "UserTable", [
        {"UserEmail": email, "UserName": name, "UserPasswordHash": password_hash, "UserDefaultCity_FK": city_ids[city]}
        for name, email, city in USERS
    ])
    insert_rows(db, "SaveTable", [
        {"SaveUser_FK": user_ids[email], "SaveEvent_FK": event_ids[title]} for email, title in SAVES
    ])


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()  # 測試檔每次重建；若 Access 正開著這個檔案會失敗，請先關掉
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    db = engine.CreateDatabase(str(DB_PATH), DB_LANG_CHINESE_TRADITIONAL, DB_VERSION_120)
    try:
        for name, spec in TABLES.items():
            create_table(db, name, spec)
        for relation in RELATIONS:
            create_relation(db, *relation)
        seed(db)
    finally:
        db.Close()
    print(f"已建立 {DB_PATH}")


if __name__ == "__main__":
    main()
