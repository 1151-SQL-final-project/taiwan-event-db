"""探點（臺灣活動資訊管理系統）後端 API。

啟動（在專案根目錄）：
    .venv\\Scripts\\python -m uvicorn main:app --app-dir api --reload
然後用瀏覽器打開 http://127.0.0.1:8000 （網頁）或 http://127.0.0.1:8000/docs （API 測試頁）

三種角色（UserTable.UserRole）：
- 使用者：查詢、收藏
- 商家：上架、修改自己的活動與優惠，新增場館；新增或修改後一律變成「待審核」
- 管理員：審核（通過／退回）、違規下架、重新上架、統計。管理員帳號不開放註冊
Access 沒有使用者權限分級，所以角色權限都在這裡檢查（require_role）。
"""
import datetime as dt
import os
import pathlib
import urllib.parse
import uuid
from contextlib import asynccontextmanager

import pyodbc
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import security
import similar

REGIONS = ["北部", "中部", "南部", "東部", "離島"]
CATEGORY_GROUPS = ["學習類", "休閒類"]
PENDING, LISTED, REJECTED, OFFLINE = "待審核", "上架中", "已退回", "已下架"
STATUSES = [PENDING, LISTED, REJECTED, OFFLINE]
USER, MERCHANT, ADMIN = "使用者", "商家", "管理員"
# 商家上傳的活動圖片存成檔案，資料庫的 EventImageURL 只記路徑（uploads/檔名）；測試時用環境變數換成暫存資料夾
UPLOAD_DIR = pathlib.Path(os.environ.get("EVENT_UPLOAD_DIR", db.ROOT / "web" / "uploads"))
UPLOAD_MAX_BYTES = 5 * 1024 * 1024
# 允許的圖片格式：Content-Type → (副檔名, 檔案開頭的特徵位元組)，不只看 Content-Type，也檢查檔案內容
IMAGE_TYPES = {
    "image/jpeg": ("jpg", (b"\xff\xd8\xff",)),
    "image/png": ("png", (b"\x89PNG\r\n\x1a\n",)),
    "image/gif": ("gif", (b"GIF87a", b"GIF89a")),
    "image/webp": ("webp", (b"RIFF",)),
}
# 管理員退回時可以勾選的理由（網頁彈窗的選項，也可以另外寫補充說明）
REJECT_REASONS = [
    "活動資訊不完整（缺少時間、地點或主辦單位）",
    "活動日期或時間有誤",
    "票價或優惠資訊有誤",
    "場館或地址有誤",
    "開賣時間有誤",
    "活動網址無法開啟或不是官方網址",
    "內容不適當或違反上架規範",
    "重複上架",
]


def auto_offline(conn) -> int:
    """自動下架：把已經結束、狀態還是上架中的活動改成已下架，回傳下架筆數。
    Access 沒有排程，所以在伺服器啟動、打開商家或管理員後台時執行；
    搜尋本身也只列還沒結束的活動，所以就算還沒執行，已結束的活動也查不到。"""
    return db.execute(conn, "admin/deactivate_ended_events")


@asynccontextmanager
async def lifespan(_app):
    try:
        with db.connect() as conn:
            count = auto_offline(conn)
        print(f"自動下架：{count} 場已結束的活動")
    except Exception as exc:  # noqa: BLE001  資料庫還沒建立時不要讓伺服器起不來
        print(f"自動下架略過：{exc}")
    yield


app = FastAPI(title="探點 API", lifespan=lifespan)


# ---------- 錯誤處理 ----------

@app.exception_handler(db.DatabaseNotFound)
def database_not_found(_request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def access_error_message(exc: pyodbc.Error) -> str:
    """取出 Access 的錯誤訊息（驗證規則的 ValidationText 就在這裡）。"""
    message = str(exc.args[1]) if len(exc.args) > 1 else str(exc)
    message = message.split("]")[-1]
    return message.split(" (-")[0].strip()


# ---------- 工具 ----------

def google_maps_url(query: str) -> str:
    """Google 地圖搜尋連結。用場館名稱查會直接開到場館（地址只會標在地址的位置）；
    名稱查不到時（例如名稱含廳別、樓層），地址連結當備用。"""
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query)


def day_start(value: dt.date | None) -> dt.datetime | None:
    return dt.datetime.combine(value, dt.time.min) if value else None


def user_id_from_header(authorization: str | None) -> int | None:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return security.read_token(authorization.removeprefix("Bearer "))


def current_user(authorization: str | None = Header(default=None)) -> dict:
    """目前登入的使用者（含角色）；沒登入或登入過期回傳 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "請先登入")
    user_id = user_id_from_header(authorization)
    if user_id is None:
        raise HTTPException(401, "登入已過期，請重新登入")
    with db.connect() as conn:
        rows = db.run(conn, "user_by_id", user_id=user_id)
    if not rows:
        raise HTTPException(401, "帳號不存在，請重新登入")
    return rows[0]


def optional_user(authorization: str | None = Header(default=None)) -> dict | None:
    """有登入就回傳使用者，沒登入回傳 None（活動詳情用：商家、管理員可以看還沒公開的活動）。"""
    user_id = user_id_from_header(authorization)
    if user_id is None:
        return None
    with db.connect() as conn:
        rows = db.run(conn, "user_by_id", user_id=user_id)
    return rows[0] if rows else None


def require_role(*roles: str):
    """限定角色的 API：例如 Depends(require_role("商家"))。"""
    def checker(user: dict = Depends(current_user)) -> dict:
        if user["UserRole"] not in roles:
            raise HTTPException(403, f"這個功能只開放給{'、'.join(roles)}")
        return user
    return checker


# ---------- 系統狀態、選單資料 ----------

@app.get("/api/health")
def health():
    """串接測試：確認後端連得到 Access，並查出 1 筆活動。"""
    with db.connect() as conn:
        sample = db.query(conn, "SELECT TOP 1 EventID, EventTitle FROM EventTable ORDER BY EventID")
    return {"database": str(db.DB_PATH.name), "sample_event": sample[0] if sample else None}


@app.get("/api/options")
def options():
    """搜尋頁、註冊頁、商家上架頁需要的下拉選單內容。"""
    with db.connect() as conn:
        return {
            "regions": REGIONS,
            "category_groups": CATEGORY_GROUPS,
            "statuses": STATUSES,
            "reject_reasons": REJECT_REASONS,
            "cities": db.run(conn, "list_cities"),
            "categories": db.run(conn, "list_categories"),
            "discount_types": db.run(conn, "list_discount_types"),
        }


# ---------- 活動查詢 ----------

@app.get("/api/events")
def search_events(
    region: str | None = None,
    city_id: int | None = None,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    category_id: int | None = None,
    category_group: str | None = None,
    discount_type_id: list[int] | None = Query(default=None),
    keyword: str | None = None,
    free_only: bool = False,
    phase: str | None = Query(default=None, pattern="^(ongoing|upcoming|early_bird)$"),
    sort: str = Query(default="date", pattern="^(date|price|ending|sale)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """依地區／縣市、日期區間、類別（或學習類／休閒類）、優惠類型、關鍵字搜尋上架中的活動。

    只列出「上架中」而且還沒結束的活動（條件寫在 sql/search_events.sql）。
    活動狀態 phase：ongoing 進行中（已經開始）；upcoming 即將開始／開賣（還沒開始，或還沒開賣）；
    early_bird 早鳥即將截止（有 14 天內截止的早鳥優惠，和 early_bird_ending_soon.sql 相同）。
    排序 sort：date 進行中的優先、再依開始日期；price 原價由低到高（票價未公布的排最後）；ending 快結束的排前面；
    sale 還沒開賣的依開賣時間排前面，其他排後面。
    回傳 {total 總筆數, page, page_size, items 這一頁的活動}。
    """
    sql, _ = db.load_sql("search_events")
    conditions, params = [], []

    if region:
        if region not in REGIONS:
            raise HTTPException(400, "地區只能是 北部、中部、南部、東部、離島")
        conditions.append("ci.CityRegion = ?")
        params.append(region)
    if city_id is not None:
        conditions.append("v.VenueCity_FK = ?")
        params.append(city_id)
    # 活動期間和查詢區間有重疊就算：開始日 <= 查詢迄日 且 結束日 >= 查詢起日
    if date_to:
        conditions.append("e.EventStartDate <= ?")
        params.append(dt.datetime.combine(date_to, dt.time.max))
    if date_from:
        conditions.append("e.EventEndDate >= ?")
        params.append(day_start(date_from))
    if category_id is not None:
        conditions.append("e.EventCategory_FK = ?")
        params.append(category_id)
    if category_group:
        if category_group not in CATEGORY_GROUPS:
            raise HTTPException(400, "類別分組只能是 學習類、休閒類")
        conditions.append("c.CategoryGroup = ?")
        params.append(category_group)
    if discount_type_id:
        placeholders = ", ".join("?" * len(discount_type_id))
        conditions.append(
            "EXISTS (SELECT 1 FROM DiscountTable AS d2"
            " WHERE d2.DiscountEvent_FK = e.EventID"
            f" AND d2.DiscountType_FK IN ({placeholders})"
            " AND (d2.DiscountStartDate IS NULL OR d2.DiscountStartDate <= Date())"
            " AND (d2.DiscountEndDate IS NULL OR d2.DiscountEndDate >= Date()))"
        )
        params.extend(discount_type_id)
    if keyword:
        conditions.append("(e.EventTitle LIKE ? OR v.VenueName LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    if free_only:
        conditions.append("e.EventOriginalPrice = 0")
    if phase == "ongoing":
        conditions.append("e.EventStartDate <= Date()")
    elif phase == "upcoming":
        conditions.append("(e.EventStartDate > Date() OR e.EventSaleStartDate > Now())")
    elif phase == "early_bird":
        conditions.append(
            "EXISTS (SELECT 1 FROM DiscountTable AS d3"
            " INNER JOIN DiscountTypeTable AS t3 ON d3.DiscountType_FK = t3.DiscountTypeID"
            " WHERE d3.DiscountEvent_FK = e.EventID AND t3.DiscountTypeName = '早鳥優惠'"
            " AND d3.DiscountEndDate BETWEEN Date() AND DateAdd('d', 14, Date()))"
        )

    order_by = {
        # 進行中的活動當作「今天開始」，再依結束日排；常設展不會因為很早開始就一直排在最前面
        "date": "IIf(e.EventStartDate < Date(), Date(), e.EventStartDate), e.EventEndDate, e.EventID",
        "price": "IIf(e.EventOriginalPrice IS NULL, 1, 0), e.EventOriginalPrice, e.EventStartDate, e.EventID",
        "ending": "e.EventEndDate, e.EventID",
        "sale": "IIf(e.EventSaleStartDate > Now(), 0, 1), e.EventSaleStartDate, e.EventStartDate, e.EventID",
    }[sort]
    sql += "".join(f"\n  AND {c}" for c in conditions) + f"\nORDER BY {order_by}"

    with db.connect() as conn:
        # Access 沒有 OFFSET，資料量不大（約一千多筆），直接取回再切出這一頁
        all_events = db.query(conn, sql, params)
    events = all_events[(page - 1) * page_size: page * page_size]
    return {"total": len(all_events), "page": page, "page_size": page_size, "items": events}


def load_event(conn, event_id: int) -> dict:
    """活動詳情＋優惠＋地圖連結；找不到回傳 404。"""
    rows = db.run(conn, "event_detail", event_id=event_id)
    if not rows:
        raise HTTPException(404, "找不到這個活動")
    event = rows[0]
    event["GoogleMapsURL"] = google_maps_url(event["VenueName"])
    event["GoogleMapsAddressURL"] = google_maps_url(event["VenueAddress"])
    event["IsEnded"] = event["EventEndDate"].date() < dt.date.today()
    event["IsOnSale"] = event["EventSaleStartDate"] is None or event["EventSaleStartDate"] <= dt.datetime.now()
    event["Discounts"] = db.run(conn, "event_discounts", event_id=event_id)
    for d in event["Discounts"]:
        d["IsValidNow"] = bool(d["IsValidNow"])  # Access 的 True 是 -1
    return event


@app.get("/api/events/{event_id}")
def event_detail(event_id: int, user: dict | None = Depends(optional_user)):
    """一般人只看得到上架中的活動；上架的商家和管理員可以看任何狀態（審核前預覽）。"""
    with db.connect() as conn:
        event = load_event(conn, event_id)
    can_preview = user and (user["UserRole"] == ADMIN or user["UserID"] == event["EventOrganizer_FK"])
    if event["EventStatus"] != LISTED and not can_preview:
        raise HTTPException(404, "找不到這個活動，或活動已經下架")
    return event


# ---------- 統計、提醒 ----------

@app.get("/api/stats")
def stats():
    """數據頁：各類別上架中的活動數（加總就是上架總數），以及熱門收藏排行。"""
    with db.connect() as conn:
        return {
            "categories": db.run(conn, "stats_events_by_category"),
            "popular": db.run(conn, "popular_saves"),
        }


@app.get("/api/discounts/early-bird")
def early_bird_ending_soon(days: int = Query(default=14, ge=1, le=90)):
    """N 天內截止的早鳥優惠。"""
    with db.connect() as conn:
        return db.run(conn, "early_bird_ending_soon", days=days)


@app.get("/api/sales/upcoming")
def sale_starting_soon(days: int = Query(default=14, ge=1, le=90)):
    """N 天內開賣的活動（熱門演唱會一開賣就賣完，提早知道開賣時間）。"""
    with db.connect() as conn:
        return db.run(conn, "sale_starting_soon", days=days)


# ---------- 註冊與登入 ----------

class RegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    role: str = USER


class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterBody):
    if body.role not in (USER, MERCHANT):  # 管理員不開放註冊
        raise HTTPException(400, "身分只能選「使用者」或「商家」")
    email = body.email.strip().lower()
    with db.connect() as conn:
        if db.run(conn, "user_by_email", email=email):
            raise HTTPException(409, "這個信箱已經註冊過了")
        try:
            db.execute(conn, "insert_user", name=body.name.strip(), email=email,
                       password_hash=security.hash_password(body.password),
                       role=body.role)
        except pyodbc.Error as exc:  # 例如信箱格式不符合驗證規則、縣市編號不存在
            raise HTTPException(400, access_error_message(exc)) from exc
        user_id = db.last_id(conn)
    return {"token": security.make_token(user_id), "user_id": user_id, "role": body.role}


@app.post("/api/auth/login")
def login(body: LoginBody):
    with db.connect() as conn:
        rows = db.run(conn, "user_by_email", email=body.email.strip().lower())
    if not rows or not security.verify_password(body.password, rows[0]["UserPasswordHash"]):
        raise HTTPException(401, "信箱或密碼錯誤")
    user = rows[0]
    return {"token": security.make_token(user["UserID"]), "user_id": user["UserID"], "role": user["UserRole"]}


@app.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


class NameBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)


@app.put("/api/me")
def update_my_name(body: NameBody, user: dict = Depends(current_user)):
    """修改名稱：使用者的暱稱、商家的商家名稱（活動頁顯示的商家名稱）。"""
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "名稱不能空白")
    with db.connect() as conn:
        db.execute(conn, "update_user_name", name=name, user_id=user["UserID"])
        return db.run(conn, "user_by_id", user_id=user["UserID"])[0]


# ---------- 使用者：收藏 ----------

@app.get("/api/saves")
def list_saves(user: dict = Depends(require_role(USER))):
    with db.connect() as conn:
        return db.run(conn, "list_saves", user_id=user["UserID"])


@app.get("/api/saves/reminders")
def save_reminders(days: int = Query(default=7, ge=1, le=90), user: dict = Depends(require_role(USER))):
    """我收藏的活動中，N 天內就要截止的優惠。"""
    with db.connect() as conn:
        return db.run(conn, "save_reminders", user_id=user["UserID"], days=days)


@app.get("/api/saves/sale-reminders")
def save_sale_reminders(days: int = Query(default=14, ge=1, le=90), user: dict = Depends(require_role(USER))):
    """我收藏的活動中，N 天內就要開賣的。"""
    with db.connect() as conn:
        return db.run(conn, "save_sale_reminders", user_id=user["UserID"], days=days)


@app.post("/api/saves/{event_id}", status_code=201)
def add_save(event_id: int, user: dict = Depends(require_role(USER))):
    with db.connect() as conn:
        event = db.run(conn, "event_detail", event_id=event_id)
        if not event or event[0]["EventStatus"] != LISTED:
            raise HTTPException(404, "找不到這個活動，或活動已經下架")
        try:
            db.execute(conn, "insert_save", user_id=user["UserID"], event_id=event_id)
        except pyodbc.IntegrityError as exc:  # 複合唯一索引擋下重複收藏
            raise HTTPException(409, "已經收藏過這個活動") from exc
    return {"saved": True}


@app.delete("/api/saves/{event_id}")
def remove_save(event_id: int, user: dict = Depends(require_role(USER))):
    with db.connect() as conn:
        db.execute(conn, "delete_save", user_id=user["UserID"], event_id=event_id)
    return {"saved": False}


# ---------- 商家後台 ----------

class DiscountBody(BaseModel):
    discount_type_id: int
    price: int = Field(ge=0)
    description: str | None = Field(default=None, max_length=100)
    start_date: dt.date | None = None
    end_date: dt.date | None = None


class EventBody(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    category_id: int
    venue_id: int
    start_date: dt.date
    end_date: dt.date
    price: int | None = Field(default=None, ge=0)  # 全票；0 = 免費；空值 = 未公布
    url: str | None = Field(default=None, max_length=255)
    description: str | None = None
    sale_start: dt.datetime | None = None  # 開賣時間（到時、分）；空值 = 沒有提供
    image_url: str | None = Field(default=None, max_length=255)  # 上傳後的 uploads/檔名，或外部圖片網址；空值 = 用類別插圖
    discounts: list[DiscountBody] = []


class VenueBody(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    city_id: int
    address: str = Field(min_length=1, max_length=100)


def check_event_body(body: EventBody):
    if body.end_date < body.start_date:
        raise HTTPException(400, "活動結束日期不能早於開始日期")
    if body.end_date < dt.date.today():
        raise HTTPException(400, "結束日期已經過了；活動結束後會自動下架，不需要再上架")
    if body.sale_start and body.sale_start.date() > body.end_date:
        raise HTTPException(400, "開賣時間不能晚於活動結束日期")
    if body.url and not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "活動網址要以 http:// 或 https:// 開頭")
    if body.image_url and not body.image_url.startswith(("http://", "https://", "uploads/")):
        raise HTTPException(400, "圖片網址要以 http:// 或 https:// 開頭")
    for d in body.discounts:
        if d.start_date and d.end_date and d.end_date < d.start_date:
            raise HTTPException(400, "優惠截止日期不能早於開始日期")
        if body.price is not None and d.price > body.price:
            raise HTTPException(400, f"優惠價 NT${d.price} 比全票 NT${body.price} 還貴")


def event_params(body: EventBody) -> dict:
    return {
        "category_id": body.category_id, "venue_id": body.venue_id, "title": body.title.strip(),
        "start_date": day_start(body.start_date), "end_date": day_start(body.end_date), "price": body.price,
        "url": (body.url or "").strip() or None, "description": (body.description or "").strip() or None,
        "sale_start": body.sale_start.replace(tzinfo=None, second=0, microsecond=0) if body.sale_start else None,
        "image_url": (body.image_url or "").strip() or None,
    }


def save_discounts(conn, event_id: int, discounts: list[DiscountBody]):
    """這場活動的優惠整批換成新的（先刪再新增）。早鳥沒填截止日等錯誤會被資料表驗證規則擋下。"""
    db.execute(conn, "merchant/delete_event_discounts", event_id=event_id)
    for d in discounts:
        db.execute(conn, "insert_discount", event_id=event_id, discount_type_id=d.discount_type_id,
                   description=(d.description or "").strip() or None, price=d.price,
                   start_date=day_start(d.start_date), end_date=day_start(d.end_date))


@app.get("/api/venues")
def list_venues(_user: dict = Depends(require_role(MERCHANT, ADMIN))):
    with db.connect() as conn:
        return db.run(conn, "list_venues")


@app.post("/api/venues", status_code=201)
def create_venue(body: VenueBody, _user: dict = Depends(require_role(MERCHANT, ADMIN))):
    with db.connect() as conn:
        try:
            db.execute(conn, "insert_venue", name=body.name.strip(), city_id=body.city_id, address=body.address.strip())
        except pyodbc.Error as exc:
            raise HTTPException(400, access_error_message(exc)) from exc
        return {"venue_id": db.last_id(conn)}


class SimilarCheckBody(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    venue_id: int
    start_date: dt.date
    end_date: dt.date
    url: str | None = None
    event_id: int | None = None  # 修改活動時填，比對時排除自己


@app.post("/api/merchant/events/similar")
def merchant_similar_events(body: SimilarCheckBody, user: dict = Depends(require_role(MERCHANT))):
    """送出審核前先檢查：系統裡有沒有相似的活動（規則和管理員審核時相同，見 api/similar.py）。
    只回傳已上架的活動，和這個商家自己的活動（其他商家還在待審核的活動不公開）。"""
    with db.connect() as conn:
        venue = next((v for v in db.run(conn, "list_venues") if v["VenueID"] == body.venue_id), None)
        if venue is None:
            raise HTTPException(400, "找不到這個場館")
        candidates = db.run(conn, "admin/similar_events", event_id=body.event_id or 0,
                            start_date=day_start(body.start_date), end_date=day_start(body.end_date))
    event = {"EventTitle": body.title, "EventVenue_FK": body.venue_id, "CityName": venue["CityName"],
             "EventURL": (body.url or "").strip() or None}
    visible = [c for c in candidates if c["EventStatus"] == LISTED or c["EventOrganizer_FK"] == user["UserID"]]
    return similar.find_similar(event, visible)[:5]


@app.get("/api/merchant/events")
def merchant_events(user: dict = Depends(require_role(MERCHANT))):
    """我上架的所有活動（各種審核狀態）。打開後台時順便執行自動下架。"""
    with db.connect() as conn:
        auto_offline(conn)
        return db.run(conn, "merchant/list_my_events", organizer_id=user["UserID"])


@app.get("/api/merchant/summary")
def merchant_summary(user: dict = Depends(require_role(MERCHANT))):
    """商家後台狀態分頁的場數與總收藏：我的活動依審核狀態分組（GROUP BY）。"""
    with db.connect() as conn:
        return {"by_status": db.run(conn, "merchant/my_stats_by_status", organizer_id=user["UserID"])}


@app.get("/api/merchant/venue-events")
def merchant_venue_events(venue_id: int, start_date: dt.date, end_date: dt.date, event_id: int = 0,
                          _user: dict = Depends(require_role(MERCHANT))):
    """上架表單選好場館和日期後，列出同場館、日期重疊的已上架活動（避免撞期）。"""
    if end_date < start_date:
        return []
    with db.connect() as conn:
        return db.run(conn, "merchant/venue_events_overlap", venue_id=venue_id, event_id=event_id,
                      start_date=day_start(start_date), end_date=day_start(end_date))


@app.post("/api/merchant/images", status_code=201)
async def merchant_upload_image(request: Request, _user: dict = Depends(require_role(MERCHANT))):
    """上傳活動圖片：請求內容直接是圖片檔（Content-Type 填圖片格式），5 MB 以內。
    存成 uploads/隨機檔名，回傳路徑，上架或修改活動時放在 image_url。"""
    kind = IMAGE_TYPES.get(request.headers.get("content-type", "").split(";")[0].strip().lower())
    if not kind:
        raise HTTPException(400, "只能上傳 JPG、PNG、WebP 或 GIF 圖片")
    data = await request.body()
    if not data:
        raise HTTPException(400, "沒有收到圖片")
    if len(data) > UPLOAD_MAX_BYTES:
        raise HTTPException(400, "圖片要在 5 MB 以內")
    ext, signatures = kind
    if not data.startswith(signatures) or (ext == "webp" and data[8:12] != b"WEBP"):
        raise HTTPException(400, "檔案內容不是這種格式的圖片")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return {"url": f"uploads/{name}"}


@app.post("/api/merchant/events", status_code=201)
def merchant_create_event(body: EventBody, user: dict = Depends(require_role(MERCHANT))):
    """上架活動（含多筆優惠）。新活動一律是「待審核」，管理員通過後才會公開。"""
    check_event_body(body)
    with db.connect() as conn:  # 活動和優惠在同一個交易裡，任何一筆失敗就全部取消
        try:
            db.execute(conn, "merchant/insert_event", organizer_id=user["UserID"], **event_params(body))
            event_id = db.last_id(conn)
            save_discounts(conn, event_id, body.discounts)
        except pyodbc.Error as exc:
            raise HTTPException(400, access_error_message(exc)) from exc
    return {"event_id": event_id, "status": PENDING}


@app.put("/api/merchant/events/{event_id}")
def merchant_update_event(event_id: int, body: EventBody, user: dict = Depends(require_role(MERCHANT))):
    """修改自己的活動與優惠；修改後回到「待審核」，管理員重新通過才會再公開。"""
    check_event_body(body)
    with db.connect() as conn:
        try:
            changed = db.execute(conn, "merchant/update_event", event_id=event_id, organizer_id=user["UserID"],
                                 **event_params(body))
            if not changed:
                raise HTTPException(404, "找不到這個活動，或不是你上架的活動")
            save_discounts(conn, event_id, body.discounts)
        except pyodbc.Error as exc:
            raise HTTPException(400, access_error_message(exc)) from exc
    return {"event_id": event_id, "status": PENDING}


# 商家上傳的圖片（資料夾可能不在 web/ 底下，所以另外掛；check_dir=False：還沒有人上傳時資料夾不存在）
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="uploads")
# 網頁：http://127.0.0.1:8000/ 直接開 web/index.html（放最後，才不會蓋掉 /api 路徑）
app.mount("/", StaticFiles(directory=db.ROOT / "web", html=True), name="web")
