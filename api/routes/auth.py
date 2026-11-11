"""註冊、登入、目前登入的帳號（修改名稱）。"""
import pyodbc
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

import db
import security
from common import MERCHANT, USER, access_error_message, current_user

router = APIRouter()


class RegisterBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)
    email: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=128)
    role: str = USER


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/api/auth/register", status_code=201)
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


@router.post("/api/auth/login")
def login(body: LoginBody):
    with db.connect() as conn:
        rows = db.run(conn, "user_by_email", email=body.email.strip().lower())
    if not rows or not security.verify_password(body.password, rows[0]["UserPasswordHash"]):
        raise HTTPException(401, "信箱或密碼錯誤")
    user = rows[0]
    return {"token": security.make_token(user["UserID"]), "user_id": user["UserID"], "role": user["UserRole"]}


@router.get("/api/me")
def me(user: dict = Depends(current_user)):
    return user


class NameBody(BaseModel):
    name: str = Field(min_length=1, max_length=20)


@router.put("/api/me")
def update_my_name(body: NameBody, user: dict = Depends(current_user)):
    """修改名稱：使用者的暱稱、商家的商家名稱（活動頁顯示的商家名稱）。"""
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "名稱不能空白")
    with db.connect() as conn:
        db.execute(conn, "update_user_name", name=name, user_id=user["UserID"])
        return db.run(conn, "user_by_id", user_id=user["UserID"])[0]
