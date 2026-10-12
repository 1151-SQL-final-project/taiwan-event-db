"""臺灣活動資訊管理系統 後端 API。

啟動（在專案根目錄）：
    .venv\\Scripts\\python -m uvicorn main:app --app-dir api --reload
然後用瀏覽器打開 http://127.0.0.1:8000 （網頁）或 http://127.0.0.1:8000/docs （API 測試頁）
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

app = FastAPI(title="臺灣活動資訊管理系統 API")

REGIONS = {"北部", "中部", "南部", "東部", "離島"}


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

def hyperlink_address(value: str | None) -> str | None:
    """Access 超連結欄位存成「顯示文字#網址#」，只取出網址。"""
    if not value:
        return None
    parts = value.split("#")
    return parts[1] if len(parts) > 1 and parts[1] else parts[0]


def google_maps_url(address: str) -> str:
    return "https://www.google.com/maps/search/?api=1&query=" + urllib.parse.quote(address)


def current_user_id(authorization: str | None = Header(default=None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "請先登入")
    user_id = security.read_token(authorization.removeprefix("Bearer "))
    if user_id is None:
        raise HTTPException(401, "登入已過期，請重新登入")
    return user_id


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
            "regions": sorted(REGIONS, key=["北部", "中部", "南部", "東部", "離島"].index),
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
    discount_type_id: list[int] | None = Query(default=None),
    keyword: str | None = None,
):
    """依地區／縣市、日期區間、類別、優惠類型、關鍵字搜尋上架中的活動。"""
    sql, _ = db.load_sql("search_events")
    conditions, params = [], []

    venue_exists = (
        "EXISTS (SELECT 1 FROM (SessionTable AS s"
        " INNER JOIN VenueTable AS v ON s.SessionVenue_FK = v.VenueID)"
        " INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID"
        " WHERE s.SessionEvent_FK = e.EventID AND {})"
    )
    if region:
        if region not in REGIONS:
            raise HTTPException(400, "地區只能是 北部、中部、南部、東部、離島")
        conditions.append(venue_exists.format("ci.CityRegion = ?"))
        params.append(region)
    if city_id is not None:
        conditions.append(venue_exists.format("v.VenueCity_FK = ?"))
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
        events = db.query(conn, sql, params)
        # 每個活動附上舉辦的場館與縣市（可能不只一個）
        if events:
            ids = [e["EventID"] for e in events]
            venues = db.query(
                conn,
                "SELECT DISTINCT s.SessionEvent_FK, v.VenueName, ci.CityName"
                " FROM (SessionTable AS s INNER JOIN VenueTable AS v ON s.SessionVenue_FK = v.VenueID)"
                " INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID"
                f" WHERE s.SessionEvent_FK IN ({', '.join('?' * len(ids))})",
                ids,
            )
            by_event: dict[int, list] = {}
            for v in venues:
                by_event.setdefault(v["SessionEvent_FK"], []).append(
                    {"VenueName": v["VenueName"], "CityName": v["CityName"]}
                )
            for e in events:
                e["Venues"] = by_event.get(e["EventID"], [])
    return events


@app.get("/api/events/{event_id}")
def event_detail(event_id: int):
    with db.connect() as conn:
        rows = db.run(conn, "event_detail", event_id=event_id)
        if not rows:
            raise HTTPException(404, "找不到這個活動")
        event = rows[0]
        event["EventURL"] = hyperlink_address(event["EventURL"])
        event["Sessions"] = db.run(conn, "event_sessions", event_id=event_id)
        for s in event["Sessions"]:
            s["GoogleMapsURL"] = google_maps_url(s["VenueAddress"])
        event["Discounts"] = db.run(conn, "event_discounts", event_id=event_id)
        for d in event["Discounts"]:
            d["IsValidNow"] = bool(d["IsValidNow"])  # Access 的 True 是 -1
    return event


# ---------- 註冊與登入 ----------

class RegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    default_city_id: int | None = None


class LoginBody(BaseModel):
    email: str
    password: str


@app.post("/api/auth/register", status_code=201)
def register(body: RegisterBody):
    email = body.email.strip().lower()
    with db.connect() as conn:
        if db.run(conn, "user_by_email", email=email):
            raise HTTPException(409, "這個信箱已經註冊過了")
        try:
            db.run(conn, "insert_user", name=body.name.strip(), email=email,
                   password_hash=security.hash_password(body.password),
                   default_city_id=body.default_city_id)
        except pyodbc.Error as exc:  # 例如信箱格式不符合驗證規則、縣市編號不存在
            raise HTTPException(400, access_error_message(exc)) from exc
        user_id = db.query(conn, "SELECT @@IDENTITY AS NewID")[0]["NewID"]
    return {"token": security.make_token(user_id), "user_id": user_id}


@app.post("/api/auth/login")
def login(body: LoginBody):
    with db.connect() as conn:
        rows = db.run(conn, "user_by_email", email=body.email.strip().lower())
    if not rows or not security.verify_password(body.password, rows[0]["UserPasswordHash"]):
        raise HTTPException(401, "信箱或密碼錯誤")
    return {"token": security.make_token(rows[0]["UserID"]), "user_id": rows[0]["UserID"]}


@app.get("/api/me")
def me(user_id: int = Depends(current_user_id)):
    with db.connect() as conn:
        rows = db.run(conn, "user_by_id", user_id=user_id)
    if not rows:
        raise HTTPException(401, "帳號不存在，請重新登入")
    return rows[0]


# ---------- 收藏 ----------

@app.get("/api/saves")
def list_saves(user_id: int = Depends(current_user_id)):
    with db.connect() as conn:
        return db.run(conn, "list_saves", user_id=user_id)


@app.post("/api/saves/{event_id}", status_code=201)
def add_save(event_id: int, user_id: int = Depends(current_user_id)):
    with db.connect() as conn:
        try:
            db.run(conn, "insert_save", user_id=user_id, event_id=event_id)
        except pyodbc.IntegrityError as exc:
            # 複合唯一索引擋下重複收藏，或活動不存在（關聯完整性）
            if db.run(conn, "event_detail", event_id=event_id):
                raise HTTPException(409, "已經收藏過這個活動") from exc
            raise HTTPException(404, "找不到這個活動") from exc
    return {"saved": True}


@app.delete("/api/saves/{event_id}")
def remove_save(event_id: int, user_id: int = Depends(current_user_id)):
    with db.connect() as conn:
        db.run(conn, "delete_save", user_id=user_id, event_id=event_id)
    return {"saved": False}


# 網頁：http://127.0.0.1:8000/ 直接開 web/index.html（放最後，才不會蓋掉 /api 路徑）
app.mount("/", StaticFiles(directory=db.ROOT / "web", html=True), name="web")
