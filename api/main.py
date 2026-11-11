"""探點（臺灣活動資訊管理系統）後端 API。

啟動（在專案根目錄）：
    .venv\\Scripts\\python -m uvicorn main:app --app-dir api --reload
然後用瀏覽器打開 http://127.0.0.1:8000 （網頁）或 http://127.0.0.1:8000/docs （API 測試頁）

三種角色（UserTable.UserRole）：
- 使用者：查詢、收藏
- 商家：上架、修改自己的活動與優惠，新增場館；新增或修改後一律變成「待審核」
- 管理員：審核（通過／退回）、違規下架、重新上架、統計。管理員帳號不開放註冊
Access 沒有使用者權限分級，所以角色權限在後端檢查（api/common.py 的 require_role）。
"""
import datetime as dt
import uuid
from contextlib import asynccontextmanager

import pyodbc
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import db
import similar
from common import (ADMIN, IMAGE_TYPES, LISTED, MERCHANT, OFFLINE, PENDING, REJECTED, STATUSES, UPLOAD_DIR,
                    UPLOAD_MAX_BYTES, access_error_message, auto_offline, day_start, load_event, require_role)
from routes import auth, public, saves


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


for module in (public, auth, saves):
    app.include_router(module.router)


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


# ---------- 管理員後台 ----------

class StatusBody(BaseModel):
    status: str
    reason: str | None = Field(default=None, max_length=255)  # 退回時必填：勾選的理由＋補充說明


# 管理員可以做的狀態變更：(原本的狀態, 新狀態)。被退回的活動要由商家修改後重新送審
ALLOWED_CHANGES = {
    (PENDING, LISTED): "通過審核",
    (PENDING, REJECTED): "退回",
    (LISTED, OFFLINE): "違規下架",
    (OFFLINE, LISTED): "重新上架",
}


@app.get("/api/admin/events")
def admin_events(
    status: str | None = None,
    keyword: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=200),
    _user: dict = Depends(require_role(ADMIN)),
):
    """所有活動，可依審核狀態、關鍵字篩選；待審核的最早送出的排前面，其他最新的排前面。
    打開後台時先執行自動下架，回傳 auto_offlined 是這次下架的筆數。"""
    sql, _ = db.load_sql("admin/list_events")
    conditions, params = [], []
    if status:
        if status not in STATUSES:
            raise HTTPException(400, "審核狀態不正確")
        conditions.append("e.EventStatus = ?")
        params.append(status)
    if keyword:
        conditions.append("(e.EventTitle LIKE ? OR u.UserName LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY e.EventID" if status == PENDING else " ORDER BY e.EventID DESC"
    with db.connect() as conn:
        offlined = auto_offline(conn)
        rows = db.query(conn, sql, params)
        counts = {r["EventStatus"]: r["EventCount"] for r in db.run(conn, "admin/stats_events_by_status")}
        items = rows[(page - 1) * page_size: page * page_size]
        for item in items:  # 待審核的活動附上可能重複的活動，審核時提醒管理員
            if item["EventStatus"] == PENDING:
                item["Similar"] = find_similar_events(conn, item["EventID"])
    return {"total": len(rows), "page": page, "page_size": page_size, "auto_offlined": offlined,
            "counts": {s: counts.get(s, 0) for s in STATUSES}, "items": items}


def find_similar_events(conn, event_id: int) -> list[dict]:
    """和這場活動日期重疊、名稱相似（加上場館、縣市）的其他已上架或待審核活動。"""
    rows = db.run(conn, "event_detail", event_id=event_id)
    if not rows:
        raise HTTPException(404, "找不到這個活動")
    event = rows[0]
    candidates = db.run(conn, "admin/similar_events", event_id=event_id,
                        start_date=event["EventStartDate"], end_date=event["EventEndDate"])
    return similar.find_similar(event, candidates)[:5]


@app.get("/api/admin/events/{event_id}/similar")
def admin_similar_events(event_id: int, _user: dict = Depends(require_role(ADMIN))):
    """可能重複上架的活動（名稱相似、日期重疊，加上同場館或同縣市），最多 5 筆。"""
    with db.connect() as conn:
        return find_similar_events(conn, event_id)


@app.get("/api/admin/events/{event_id}/review")
def admin_review_event(event_id: int, _user: dict = Depends(require_role(ADMIN))):
    """審核畫面一次要的資料：活動詳情（含優惠）、可能重複的活動（待審核才查）、上架者其他活動各狀態的場數。"""
    with db.connect() as conn:
        event = load_event(conn, event_id)
        return {
            "event": event,
            "similar": find_similar_events(conn, event_id) if event["EventStatus"] == PENDING else [],
            "organizer_history": db.run(conn, "admin/organizer_history",
                                        organizer_id=event["EventOrganizer_FK"], event_id=event_id),
        }


@app.post("/api/admin/events/{event_id}/status")
def admin_set_status(event_id: int, body: StatusBody, _user: dict = Depends(require_role(ADMIN))):
    """審核（待審核 → 上架中／已退回）、違規下架（上架中 → 已下架）、重新上架（已下架 → 上架中）。
    退回時要附上理由（reason），商家在後台看得到；其他狀態不記理由。"""
    if body.status not in STATUSES:
        raise HTTPException(400, "審核狀態不正確")
    reason = (body.reason or "").strip() or None
    if body.status == REJECTED and not reason:
        raise HTTPException(400, "請選擇退回理由")
    with db.connect() as conn:
        rows = db.run(conn, "event_detail", event_id=event_id)
        if not rows:
            raise HTTPException(404, "找不到這個活動")
        event = rows[0]
        action = ALLOWED_CHANGES.get((event["EventStatus"], body.status))
        if not action:
            raise HTTPException(400, f"「{event['EventStatus']}」的活動不能改成「{body.status}」")
        if body.status == LISTED and event["EventEndDate"].date() < dt.date.today():
            raise HTTPException(400, "這場活動已經結束，不能上架")
        db.execute(conn, "admin/update_event_status", status=body.status,
                   reason=reason if body.status == REJECTED else None, event_id=event_id)
    return {"event_id": event_id, "status": body.status, "action": action}


# 商家上傳的圖片（資料夾可能不在 web/ 底下，所以另外掛；check_dir=False：還沒有人上傳時資料夾不存在）
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="uploads")
# 網頁：http://127.0.0.1:8000/ 直接開 web/index.html（放最後，才不會蓋掉 /api 路徑）
app.mount("/", StaticFiles(directory=db.ROOT / "web", html=True), name="web")
