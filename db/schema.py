"""資料表結構（8 張表）與基本對照資料。build_test_db.py、build_db.py 共用。

- 資料表、欄位型態、驗證規則、預設值、查閱欄位、關聯都照
  HW1_TableSchemaSketch_41411016E_修改版.xlsx（10/16 版，說明見 docs/schema.md）。
- 透過 DAO（Access 內建的資料庫引擎介面）建表，因為驗證規則、
  預設值、查閱欄位這些設定，用 SQL 的 CREATE TABLE 做不到。
"""
import datetime as dt
import pathlib

import win32com.client

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
# 狀態與角色（驗證規則、後端程式都用這幾個值）
EVENT_STATUSES = ["待審核", "上架中", "已退回", "已下架"]
USER_ROLES = ["使用者", "商家", "管理員"]
CATEGORY_GROUPS = ["學習類", "休閒類"]


def _in_rule(values):
    return "In (" + ",".join(f'"{v}"' for v in values) + ")"


TABLES = {
    "CategoryTable": {
        "fields": [
            ("CategoryID", "auto", None, {"caption": "類別編號"}),
            ("CategoryName", DB_TEXT, 20, {"caption": "類別名稱", "required": True}),
            # 學習類：展覽、講座、工作坊、科普展覽、研習營隊，讓使用者一次查所有「課堂之外的學習機會」
            ("CategoryGroup", DB_TEXT, 10, {
                "caption": "類別分組", "required": True,
                "rule": _in_rule(CATEGORY_GROUPS), "rule_text": "類別分組只能是 學習類、休閒類",
            }),
        ],
        "unique": [["CategoryName"]],
        "index": ["CategoryGroup"],
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
    "UserTable": {
        "fields": [
            ("UserID", "auto", None, {"caption": "使用者編號"}),
            ("UserName", DB_TEXT, 20, {"caption": "使用者暱稱", "required": True}),
            ("UserEmail", DB_TEXT, 50, {
                "caption": "使用者登入信箱", "required": True,
                "rule": 'Like "*@*.*"', "rule_text": "請輸入正確的電子郵件格式",
            }),
            ("UserPasswordHash", DB_TEXT, 255, {"caption": "使用者密碼雜湊值", "required": True}),
            # 註冊時只能選使用者或商家；管理員帳號由系統建立。各角色能做什麼由後端檢查（Access 沒有權限分級）
            ("UserRole", DB_TEXT, 10, {
                "caption": "使用者角色", "required": True, "default": '"使用者"',
                "rule": _in_rule(USER_ROLES), "rule_text": "使用者角色只能是 使用者、商家、管理員",
            }),
        ],
        "unique": [["UserEmail"]],
        "index": ["UserRole"],
    },
    "EventTable": {
        "fields": [
            ("EventID", "auto", None, {"caption": "活動編號"}),
            ("EventCategory_FK", DB_LONG, None, {
                "caption": "活動所屬類別", "required": True,
                "lookup": ("CategoryTable", "CategoryID", "CategoryName"),
            }),
            # 縣市與地址由場館表取得；同一場活動在多個場館舉辦時，每個場館各建一筆活動
            ("EventVenue_FK", DB_LONG, None, {
                "caption": "活動舉辦場館", "required": True,
                "lookup": ("VenueTable", "VenueID", "VenueName"),
            }),
            ("EventTitle", DB_TEXT, 100, {"caption": "活動名稱", "required": True}),
            ("EventStartDate", DB_DATE, None, {"caption": "活動開始日期", "required": True, "format": "yyyy/mm/dd"}),
            # 不另設下架日期：過了結束日期就自動下架
            ("EventEndDate", DB_DATE, None, {"caption": "活動結束日期", "required": True, "format": "yyyy/mm/dd"}),
            # 只填全票價格；0 = 免費；空值 = 主辦單位未公布。學生票、敬老票等其他票價記在 DiscountTable
            ("EventOriginalPrice", DB_LONG, None, {
                "caption": "活動原價（全票）",
                "rule": ">=0", "rule_text": "票價不能是負數（免費請填 0，未公布請留空）",
            }),
            # 用短文字而非超連結型態：超連結透過 ODBC 讀出會變成「顯示文字#網址#」
            ("EventURL", DB_TEXT, 255, {"caption": "活動官方網址"}),
            ("EventDataSource", DB_TEXT, 50, {"caption": "資料來源", "required": True}),
            # 上架的商家；文化部開放資料匯入的活動沒有商家，一律填管理員帳號。只能是商家或管理員（由後端檢查）
            ("EventOrganizer_FK", DB_LONG, None, {
                "caption": "上架商家", "required": True,
                "lookup": ("UserTable", "UserID", "UserName"),
            }),
            # 商家新增或修改後變成待審核；管理員通過才是上架中。查詢只顯示上架中且還沒結束的活動
            ("EventStatus", DB_TEXT, 10, {
                "caption": "審核狀態", "required": True, "default": '"待審核"',
                "rule": _in_rule(EVENT_STATUSES), "rule_text": "審核狀態只能是 待審核、上架中、已退回、已下架",
            }),
            ("EventDescription", DB_MEMO, None, {"caption": "活動詳細說明"}),
            # 售票平台開放購票的時間（熱門演唱會一開賣就賣完，要提早提醒）；空值 = 未提供或不用買票
            ("EventSaleStartDate", DB_DATE, None, {"caption": "開賣時間", "format": "yyyy/mm/dd hh:nn"}),
            # 管理員退回時選的理由，商家在後台看得到；商家修改送審後清空
            ("EventRejectReason", DB_TEXT, 255, {"caption": "退回理由"}),
            # 活動主視覺的網址（OPENTIX og:image 或文化部 imageUrl）；空值 = 沒有，網頁改顯示類別插圖
            ("EventImageURL", DB_TEXT, 255, {"caption": "活動圖片網址"}),
            # 場次時間，只用來顯示：開始|結束;開始|結束（yyyy-mm-ddThh:nn）。組內決定不加場次表，所以不拆成資料表
            ("EventShowTimes", DB_MEMO, None, {"caption": "場次時間"}),
        ],
        # 開賣時間最晚是活動結束日當天（EventEndDate 存的是當天 0 點，所以比較「隔天 0 點」）
        "table_rule": ("[EventEndDate]>=[EventStartDate]"
                       " And ([EventSaleStartDate] Is Null Or [EventSaleStartDate]<[EventEndDate]+1)"
                       " And ([EventRejectReason] Is Null Or [EventStatus]='已退回')",
                       "活動結束日期不能早於開始日期；開賣時間不能晚於活動結束日期；只有已退回的活動才能填退回理由"),
        "index": ["EventCategory_FK", "EventVenue_FK", "EventTitle", "EventStartDate", "EventEndDate",
                  "EventOriginalPrice", "EventOrganizer_FK", "EventStatus", "EventSaleStartDate"],
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
            # 也用來記錄全票以外的票價，例如學生票、敬老票
            ("DiscountPrice", DB_LONG, None, {
                "caption": "優惠特價金額", "required": True,
                "rule": ">=0", "rule_text": "優惠價不能是負數",
            }),
            # 開始日期空值 = 與活動期間相同；截止日期空值 = 沒有截止日（一直有效）
            ("DiscountStartDate", DB_DATE, None, {"caption": "優惠開始日期", "format": "yyyy/mm/dd"}),
            ("DiscountEndDate", DB_DATE, None, {"caption": "優惠截止日期", "format": "yyyy/mm/dd"}),
        ],
        # 早鳥優惠一定要有截止日。DiscountTypeTable 由本程式依 DISCOUNT_TYPES 的順序建立，早鳥固定是 2 號
        "table_rule": ("([DiscountEndDate]>=[DiscountStartDate] Or [DiscountEndDate] Is Null Or [DiscountStartDate] Is Null)"
                       " And ([DiscountType_FK]<>2 Or [DiscountEndDate] Is Not Null)",
                       "優惠截止日期不能早於開始日期；早鳥優惠一定要填截止日期"),
        "index": ["DiscountEvent_FK", "DiscountType_FK", "DiscountPrice", "DiscountStartDate", "DiscountEndDate"],
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
# 收藏、優惠跟著活動走：刪除活動時一起刪掉；刪除使用者時收藏一起刪。
# 其他關聯（縣市、類別、場館、優惠類型、上架商家）不允許刪除還在使用中的資料
RELATIONS = [
    ("CityTable", "CityID", "VenueTable", "VenueCity_FK", False),
    ("CategoryTable", "CategoryID", "EventTable", "EventCategory_FK", False),
    ("VenueTable", "VenueID", "EventTable", "EventVenue_FK", False),
    ("UserTable", "UserID", "EventTable", "EventOrganizer_FK", False),
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


# ---- 基本對照資料（每個資料庫都一樣）----
CITIES = [
    ("臺北市", "北部"), ("新北市", "北部"), ("基隆市", "北部"), ("桃園市", "北部"),
    ("新竹市", "北部"), ("新竹縣", "北部"),
    ("苗栗縣", "中部"), ("臺中市", "中部"), ("彰化縣", "中部"), ("南投縣", "中部"), ("雲林縣", "中部"),
    ("嘉義市", "南部"), ("嘉義縣", "南部"), ("臺南市", "南部"), ("高雄市", "南部"), ("屏東縣", "南部"),
    ("宜蘭縣", "東部"), ("花蓮縣", "東部"), ("臺東縣", "東部"),
    ("澎湖縣", "離島"), ("金門縣", "離島"), ("連江縣", "離島"),
]
CATEGORIES = [  # (類別, 分組)
    ("展覽", "學習類"), ("講座", "學習類"), ("工作坊", "學習類"), ("科普展覽", "學習類"), ("研習營隊", "學習類"),
    ("音樂表演", "休閒類"), ("戲劇", "休閒類"), ("舞蹈", "休閒類"), ("市集", "休閒類"), ("體育賽事", "休閒類"),
]
DISCOUNT_TYPES = ["學生優惠", "早鳥優惠", "敬老優惠", "團體優惠"]


def com_value(value):
    """寫進 DAO 前的轉換。pywin32 會把沒有時區的 datetime 當成本地時間（UTC+8）再轉成 UTC，
    結果存進 Access 會早 8 小時（10/15 00:00 變成 10/14 16:00）。Access 的日期沒有時區，
    所以標成 UTC，讓 pywin32 原封不動寫入。"""
    if isinstance(value, dt.datetime) and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def insert_rows(db, table, rows):
    """用 DAO Recordset 新增資料，回傳 {第一欄的值: 新的自動編號}。"""
    rs = db.OpenRecordset(table, 2)  # dbOpenDynaset
    pk = db.TableDefs(table).Indexes("PrimaryKey").Fields(0).Name
    ids = {}
    for row in rows:
        rs.AddNew()
        for col, value in row.items():
            if value is not None:
                rs.Fields(col).Value = com_value(value)
        new_id = rs.Fields(pk).Value
        rs.Update()
        ids[next(iter(row.values()))] = new_id
    rs.Close()
    return ids


def create_database(path: pathlib.Path):
    """建立空的資料庫：8 張表、關聯，加上縣市、類別、優惠類型。回傳 (db, 對照表)。"""
    if path.exists():
        path.unlink()  # 每次重建；若 Access 正開著這個檔案會失敗，請先關掉
    engine = win32com.client.Dispatch("DAO.DBEngine.120")
    db = engine.CreateDatabase(str(path), DB_LANG_CHINESE_TRADITIONAL, DB_VERSION_120)
    for name, spec in TABLES.items():
        create_table(db, name, spec)
    for relation in RELATIONS:
        create_relation(db, *relation)
    ids = {
        "city": insert_rows(db, "CityTable", [{"CityName": n, "CityRegion": r} for n, r in CITIES]),
        "category": insert_rows(db, "CategoryTable", [{"CategoryName": n, "CategoryGroup": g} for n, g in CATEGORIES]),
        "discount_type": insert_rows(db, "DiscountTypeTable", [{"DiscountTypeName": n} for n in DISCOUNT_TYPES]),
    }
    assert ids["discount_type"]["早鳥優惠"] == 2, "DISCOUNT_TYPES 順序改了，請同步修改 DiscountTable 的驗證規則"
    return db, ids
