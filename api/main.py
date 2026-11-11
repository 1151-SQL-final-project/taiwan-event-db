"""探點（臺灣活動資訊管理系統）後端 API。

啟動（在專案根目錄）：
    .venv\\Scripts\\python -m uvicorn main:app --app-dir api --reload
然後用瀏覽器打開 http://127.0.0.1:8000 （網頁）或 http://127.0.0.1:8000/docs （API 測試頁）

三種角色（UserTable.UserRole）：
- 使用者：查詢、收藏
- 商家：上架、修改自己的活動與優惠，新增場館；新增或修改後一律變成「待審核」
- 管理員：審核（通過／退回）、違規下架、重新上架、統計。管理員帳號不開放註冊
Access 沒有使用者權限分級，所以角色權限在後端檢查（api/common.py 的 require_role）。

檔案：本檔組合整個應用程式；common.py 共用常數、登入與角色檢查；
routes/ 依功能分檔：public（不用登入）、auth（註冊登入）、saves（收藏）、merchant（商家後台）、admin（管理員後台）。
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

import db
from common import UPLOAD_DIR, auto_offline
from routes import admin, auth, merchant, public, saves


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


for module in (public, auth, saves, merchant, admin):
    app.include_router(module.router)

# 商家上傳的圖片（資料夾可能不在 web/ 底下，所以另外掛；check_dir=False：還沒有人上傳時資料夾不存在）
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR, check_dir=False), name="uploads")
# 網頁：http://127.0.0.1:8000/ 直接開 web/index.html（放最後，才不會蓋掉 /api 路徑）
app.mount("/", StaticFiles(directory=db.ROOT / "web", html=True), name="web")
