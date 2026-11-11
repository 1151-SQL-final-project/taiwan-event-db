"""管理員後台：活動清單、審核面板、重複提醒、改變審核狀態（通過、退回、違規下架、重新上架）。"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

import db
import similar
from common import ADMIN, LISTED, OFFLINE, PENDING, REJECTED, STATUSES, auto_offline, load_event, require_role

router = APIRouter()


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


@router.get("/api/admin/events")
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


@router.get("/api/admin/events/{event_id}/similar")
def admin_similar_events(event_id: int, _user: dict = Depends(require_role(ADMIN))):
    """可能重複上架的活動（名稱相似、日期重疊，加上同場館或同縣市），最多 5 筆。"""
    with db.connect() as conn:
        return find_similar_events(conn, event_id)


@router.get("/api/admin/events/{event_id}/review")
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


@router.post("/api/admin/events/{event_id}/status")
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
