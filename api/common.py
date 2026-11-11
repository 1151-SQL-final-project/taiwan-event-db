"""後端共用：常數（地區、審核狀態、角色、退回理由、圖片上傳限制）、登入與角色檢查、共用的小工具。
各功能的 API 在 api/routes/，都從這裡匯入。"""
import datetime as dt
import os
import pathlib
import urllib.parse

import pyodbc
from fastapi import Depends, Header, HTTPException

import db
import security

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


# ---------- 活動詳情（活動頁和管理員審核共用） ----------

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
