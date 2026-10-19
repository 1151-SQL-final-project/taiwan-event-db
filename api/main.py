"""事集（臺灣活動資訊管理系統）後端 API。

啟動（在專案根目錄）：
    .venv\\Scripts\\python -m uvicorn main:app --app-dir api --reload
然後用瀏覽器打開 http://127.0.0.1:8000 （網頁）或 http://127.0.0.1:8000/docs （API 測試頁）

三種角色（UserTable.UserRole）：
- 使用者：查詢、收藏
- 商家：上架、修改自己的活動與優惠，新增場館；新增或修改後一律變成「待審核」
- 管理員：審核（通過／退回）、違規下架、重新上架、統計。管理員帳號不開放註冊
Access 沒有使用者權限分級，所以角色權限都在這裡檢查（require_role）。

目前完成：註冊登入（含角色）、搜尋、活動詳情、收藏。
商家後台、管理員後台的 API 已經定好路徑和參數（回傳 501「尚未實作」），
等 SQL 寫好（見 sql/README.md 的「還沒寫的查詢」）再接上。
"""
import datetime as dt
import urllib.parse

import pyodbc
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import security

# TODO（自動下架）：伺服器啟動時執行一次 sql/admin/deactivate_ended_events.sql，
# 把已結束、狀態還是上架中的活動改成已下架。可以用 FastAPI 的 lifespan 做。
# 在那之前，搜尋本身已經只列還沒結束的活動（寫在 sql/search_events.sql）。
app = FastAPI(title="事集 API")

REGIONS = ["北部", "中部", "南部", "東部", "離島"]
CATEGORY_GROUPS = ["學習類", "休閒類"]
PENDING, LISTED, REJECTED, OFFLINE = "待審核", "上架中", "已退回", "已下架"
STATUSES = [PENDING, LISTED, REJECTED, OFFLINE]
USER, MERCHANT, ADMIN = "使用者", "商家", "管理員"


# ---------- 錯誤處理 ----------

@app.exception_handler(db.DatabaseNotFound)
def database_not_found(_request, exc):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


def access_error_message(exc: pyodbc.Error) -> str:
    """取出 Access 的錯誤訊息（驗證規則的 ValidationText 就在這裡）。"""
    message = str(exc.args[1]) if len(exc.args) > 1 else str(exc)
    message = message.split("]")[-1]
    return message.split(" (-")[0].strip()


def not_implemented(what: str):
    raise HTTPException(501, f"尚未實作：{what}")


# ---------- 工具 ----------

def google_maps_url(query: str) -> str:
    """Google 地圖搜尋連結。用場館名稱查會直接開到場館（地址只會標在地址的位置）；
    名稱查不到時（例如名稱含廳別、樓層），地址連結當備用。"""
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(query)


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
    """限定角色的 API：例如 Depends(require_role("商家"))。角色不對回傳 403。"""
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
    """搜尋頁、註冊頁需要的下拉選單內容。"""
    with db.connect() as conn:
        return {
            "regions": REGIONS,
            "category_groups": CATEGORY_GROUPS,
            "statuses": STATUSES,
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
):
    """依地區／縣市、日期區間、類別（或學習類／休閒類）、優惠類型、關鍵字搜尋。
    只列出「上架中」而且還沒結束的活動（條件寫在 sql/search_events.sql）。"""
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
        params.append(dt.datetime.combine(date_from, dt.time.min))
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
        conditions.append("e.EventTitle LIKE ?")
        params.append(f"%{keyword}%")

    sql += "".join(f"\n  AND {c}" for c in conditions) + "\nORDER BY e.EventStartDate, e.EventID"
    with db.connect() as conn:
        return db.query(conn, sql, params)


@app.get("/api/events/{event_id}")
def event_detail(event_id: int, user: dict | None = Depends(optional_user)):
    """活動詳情、場館（附 Google 地圖連結）、優惠。
    一般人只看得到上架中的活動；上架的商家和管理員可以看任何狀態（審核前預覽）。"""
    with db.connect() as conn:
        rows = db.run(conn, "event_detail", event_id=event_id)
        if not rows:
            raise HTTPException(404, "找不到這個活動")
        event = rows[0]
        event["GoogleMapsURL"] = google_maps_url(event["VenueName"])
        event["GoogleMapsAddressURL"] = google_maps_url(event["VenueAddress"])
        event["Discounts"] = db.run(conn, "event_discounts", event_id=event_id)
        for d in event["Discounts"]:
            d["IsValidNow"] = bool(d["IsValidNow"])  # Access 的 True 是 -1
    can_preview = user and (user["UserRole"] == ADMIN or user["UserID"] == event["EventOrganizer_FK"])
    if event["EventStatus"] != LISTED and not can_preview:
        raise HTTPException(404, "找不到這個活動，或活動已經下架")
    return event


# ---------- 註冊與登入 ----------

class RegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    role: str = USER
    default_city_id: int | None = None


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
                       role=body.role, default_city_id=body.default_city_id)
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


# ---------- 使用者：收藏 ----------

@app.get("/api/saves")
def list_saves(user: dict = Depends(require_role(USER))):
    with db.connect() as conn:
        return db.run(conn, "list_saves", user_id=user["UserID"])


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


# ---------- 商家後台（待實作） ----------
# 路徑、參數、權限都已經定好，網頁可以先照這些格式做畫面。
# 要用到的 SQL 見 sql/README.md 的「還沒寫的查詢」。

class DiscountBody(BaseModel):
    discount_type_id: int
    price: int = Field(ge=0)
    description: str | None = Field(default=None, max_length=100)
    start_date: dt.date | None = None
    end_date: dt.date | None = None  # 早鳥優惠必填（資料表驗證規則會擋）


class EventBody(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    category_id: int
    venue_id: int
    start_date: dt.date
    end_date: dt.date
    price: int | None = Field(default=None, ge=0)  # 全票；0 = 免費；空值 = 未公布
    url: str | None = Field(default=None, max_length=255)
    description: str | None = None
    discounts: list[DiscountBody] = []


class VenueBody(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    city_id: int
    address: str = Field(min_length=1, max_length=100)


@app.get("/api/venues")
def list_venues(_user: dict = Depends(require_role(MERCHANT, ADMIN))):
    """場館清單（商家上架活動時選場館）。SQL：list_venues.sql"""
    not_implemented("場館清單")


@app.post("/api/venues", status_code=201)
def create_venue(body: VenueBody, _user: dict = Depends(require_role(MERCHANT, ADMIN))):
    """新增場館，回傳 {venue_id}。SQL：insert_venue.sql"""
    not_implemented("新增場館")


@app.get("/api/merchant/events")
def merchant_events(user: dict = Depends(require_role(MERCHANT))):
    """我上架的所有活動（各種審核狀態）。打開後台時順便執行自動下架。SQL：merchant/list_my_events.sql"""
    not_implemented("商家：我的活動")


@app.post("/api/merchant/events", status_code=201)
def merchant_create_event(body: EventBody, user: dict = Depends(require_role(MERCHANT))):
    """上架活動（含多筆優惠），一律「待審核」，回傳 {event_id, status}。
    活動和優惠要在同一個交易裡（同一個 db.connect()），任何一筆失敗就全部取消。
    SQL：merchant/insert_event.sql、insert_discount.sql"""
    not_implemented("商家：上架活動")


@app.put("/api/merchant/events/{event_id}")
def merchant_update_event(event_id: int, body: EventBody, user: dict = Depends(require_role(MERCHANT))):
    """修改自己的活動與優惠，改完回到「待審核」。只能改自己上架的（WHERE 同時比對商家編號）。
    SQL：merchant/update_event.sql、merchant/delete_event_discounts.sql、insert_discount.sql"""
    not_implemented("商家：修改活動")


# ---------- 管理員後台（待實作） ----------

class StatusBody(BaseModel):
    status: str


@app.get("/api/admin/events")
def admin_events(status: str | None = None, keyword: str | None = None,
                 _user: dict = Depends(require_role(ADMIN))):
    """所有活動，可依審核狀態、關鍵字篩選。打開後台時先執行自動下架。SQL：admin/list_events.sql"""
    not_implemented("管理員：活動清單")


@app.post("/api/admin/events/{event_id}/status")
def admin_set_status(event_id: int, body: StatusBody, _user: dict = Depends(require_role(ADMIN))):
    """審核與下架。允許的變更：待審核 → 上架中（通過）／已退回（退回）；上架中 → 已下架（違規下架）；
    已下架 → 上架中（重新上架，已結束的活動不行）。SQL：admin/update_event_status.sql"""
    not_implemented("管理員：審核與下架")


@app.get("/api/admin/stats")
def admin_stats(_user: dict = Depends(require_role(ADMIN))):
    """各審核狀態的活動數、各地區上架中的活動數、熱門收藏排行。
    SQL：admin/stats_events_by_status.sql、stats_events_by_region.sql、popular_saves.sql"""
    not_implemented("管理員：統計")


# 網頁：http://127.0.0.1:8000/ 直接開 web/index.html（放最後，才不會蓋掉 /api 路徑）
app.mount("/", StaticFiles(directory=db.ROOT / "web", html=True), name="web")
