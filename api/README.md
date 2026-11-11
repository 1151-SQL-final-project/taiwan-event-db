# api

後端程式（晨嬡負責），負責連接網頁與 Access 資料庫。

| 檔案 | 內容 |
|---|---|
| `main.py` | 啟動入口：建立 FastAPI、啟動時自動下架已結束的活動、組合 `routes/`、提供網頁與上傳的圖片 |
| `common.py` | 共用：地區、審核狀態、角色、退回理由等常數；登入與角色檢查（`require_role`）；活動詳情 |
| `routes/public.py` | 不用登入：選單資料、活動搜尋與詳情、數據、即將開賣、早鳥即將截止 |
| `routes/auth.py` | 註冊、登入、修改名稱 |
| `routes/saves.py` | 使用者的收藏與提醒 |
| `routes/merchant.py` | 商家後台：場館、上架與修改活動、上傳圖片、送出前的重複檢查 |
| `routes/admin.py` | 管理員後台：活動清單、審核面板、改變審核狀態 |
| `db.py`、`security.py`、`similar.py` | 連線 Access 與執行 `sql/`、密碼與登入 token、相似活動比對 |

啟動指令不變：`.venv\Scripts\python -m uvicorn main:app --app-dir api --reload`
