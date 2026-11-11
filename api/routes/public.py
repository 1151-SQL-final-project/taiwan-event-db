"""不用登入的 API：系統狀態、選單資料、活動搜尋與詳情、數據、即將開賣與早鳥即將截止。"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query

import db
from common import (ADMIN, CATEGORY_GROUPS, LISTED, REGIONS, REJECT_REASONS, STATUSES, day_start, load_event,
                    optional_user)

router = APIRouter()


# ---------- 系統狀態、選單資料 ----------

@router.get("/api/health")
def health():
    """串接測試：確認後端連得到 Access，並查出 1 筆活動。"""
    with db.connect() as conn:
        sample = db.query(conn, "SELECT TOP 1 EventID, EventTitle FROM EventTable ORDER BY EventID")
    return {"database": str(db.DB_PATH.name), "sample_event": sample[0] if sample else None}


@router.get("/api/options")
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

@router.get("/api/events")
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


@router.get("/api/events/{event_id}")
def event_detail(event_id: int, user: dict | None = Depends(optional_user)):
    """一般人只看得到上架中的活動；上架的商家和管理員可以看任何狀態（審核前預覽）。"""
    with db.connect() as conn:
        event = load_event(conn, event_id)
    can_preview = user and (user["UserRole"] == ADMIN or user["UserID"] == event["EventOrganizer_FK"])
    if event["EventStatus"] != LISTED and not can_preview:
        raise HTTPException(404, "找不到這個活動，或活動已經下架")
    return event


# ---------- 統計、提醒 ----------

@router.get("/api/stats")
def stats():
    """數據頁：各類別上架中的活動數（加總就是上架總數），以及熱門收藏排行。"""
    with db.connect() as conn:
        return {
            "categories": db.run(conn, "stats_events_by_category"),
            "popular": db.run(conn, "popular_saves"),
        }


@router.get("/api/discounts/early-bird")
def early_bird_ending_soon(days: int = Query(default=14, ge=1, le=90)):
    """N 天內截止的早鳥優惠。"""
    with db.connect() as conn:
        return db.run(conn, "early_bird_ending_soon", days=days)


@router.get("/api/sales/upcoming")
def sale_starting_soon(days: int = Query(default=14, ge=1, le=90)):
    """N 天內開賣的活動（熱門演唱會一開賣就賣完，提早知道開賣時間）。"""
    with db.connect() as conn:
        return db.run(conn, "sale_starting_soon", days=days)
