"""使用者的收藏：收藏清單、優惠截止與開賣提醒、加入與取消收藏。"""
import pyodbc
from fastapi import APIRouter, Depends, HTTPException, Query

import db
from common import LISTED, USER, require_role

router = APIRouter()


@router.get("/api/saves")
def list_saves(user: dict = Depends(require_role(USER))):
    with db.connect() as conn:
        return db.run(conn, "list_saves", user_id=user["UserID"])


@router.get("/api/saves/reminders")
def save_reminders(days: int = Query(default=7, ge=1, le=90), user: dict = Depends(require_role(USER))):
    """我收藏的活動中，N 天內就要截止的優惠。"""
    with db.connect() as conn:
        return db.run(conn, "save_reminders", user_id=user["UserID"], days=days)


@router.get("/api/saves/sale-reminders")
def save_sale_reminders(days: int = Query(default=14, ge=1, le=90), user: dict = Depends(require_role(USER))):
    """我收藏的活動中，N 天內就要開賣的。"""
    with db.connect() as conn:
        return db.run(conn, "save_sale_reminders", user_id=user["UserID"], days=days)


@router.post("/api/saves/{event_id}", status_code=201)
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


@router.delete("/api/saves/{event_id}")
def remove_save(event_id: int, user: dict = Depends(require_role(USER))):
    with db.connect() as conn:
        db.execute(conn, "delete_save", user_id=user["UserID"], event_id=event_id)
    return {"saved": False}
