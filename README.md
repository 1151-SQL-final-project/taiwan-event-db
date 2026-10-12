# taiwan-event-db

SQL與資料庫設計 115-1 期末專題：臺灣活動資訊管理系統

「臺灣活動彙整搜索App」的後台資料庫：整合各地區、各類型活動，依地區、時間、優惠類型快速查詢。

```
網頁 (web/)  ⇄  後端 Python FastAPI (api/)  ⇄  Access 資料庫 (db/)
                       ↑ 讀取 sql/ 裡的查詢檔
```

## 資料夾

| 資料夾 | 內容 | 負責 |
|---|---|---|
| `db/` | `build_test_db.py` 產生測試用資料庫；正式 Access 主檔之後放這裡 | 晏均（主檔） |
| `api/` | 後端：連接 Access、登入、搜尋、收藏 | 晨嬡 |
| `sql/` | 每個查詢一個 `.sql` 檔，後端直接讀取（寫法見 [sql/README.md](sql/README.md)） | 伯元 |
| `web/` | 網頁。目前是沒有設計的串接測試版，功能都能用 | 邦妤 |
| `data/` | 整理好的 CSV 資料；`data/templates/` 是建檔範本（見 [說明](data/templates/README.md)） | 俊緯、揚健 |
| `docs/` | 提案、報告、會議紀錄、引用清單；資料表修改提案見 [docs/schema-v2.md](docs/schema-v2.md) | 全組 |

## 第一次在自己電腦上執行

需要：Windows、Microsoft Office（含 Access）、[Python 3.12](https://www.python.org/downloads/)（安裝時勾選「Add python.exe to PATH」）。

**Office 和 Python 的位元數要一樣**（現在的 Office 幾乎都是 64 位元，Python 也裝 64 位元的就對了）。檢查方法：

```powershell
python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
```

在專案資料夾開啟 PowerShell（VS Code：終端機 → 新增終端機），依序執行：

```powershell
# 1. 建立虛擬環境並安裝套件（只要做一次）
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2. 產生測試用資料庫 db\test_events.accdb（之後想重置測試資料，再跑一次就好）
.venv\Scripts\python db\build_test_db.py

# 3. 啟動後端
.venv\Scripts\python -m uvicorn main:app --app-dir api --reload
```

看到 `Uvicorn running on http://127.0.0.1:8000` 就成功了：

- 網頁：<http://127.0.0.1:8000>
- API 測試頁（可以直接在瀏覽器試每一支 API）：<http://127.0.0.1:8000/docs>

停止後端：在 PowerShell 按 `Ctrl + C`。

測試帳號：`student@example.com`／`test1234`（另有 `admin@example.com`，密碼相同）。

### 改接正式資料庫

預設連 `db/test_events.accdb`。要改接其他 Access 檔，啟動前設定環境變數：

```powershell
$env:EVENT_DB_PATH = "C:\完整路徑\活動資料庫.accdb"
.venv\Scripts\python -m uvicorn main:app --app-dir api --reload
```

### 常見問題

| 狀況 | 解決方法 |
|---|---|
| `找不到資料庫檔案` | 還沒執行第 2 步，或 `EVENT_DB_PATH` 路徑打錯 |
| `Data source name not found` / `IM002` | Office 和 Python 位元數不同，或沒裝 Access。可另外安裝 [Microsoft Access Database Engine](https://www.microsoft.com/zh-tw/download/details.aspx?id=54920)（選和 Python 相同位元數的版本） |
| `build_test_db.py` 刪不掉舊檔 | 測試資料庫正在 Access 裡開著，先關掉 |
| 網頁顯示舊的內容 | 按 `Ctrl + F5` 強制重新整理 |

## API 一覽

| 方法 | 路徑 | 說明 | 需登入 |
|---|---|---|---|
| GET | `/api/health` | 串接測試：從 Access 查 1 筆活動 | |
| GET | `/api/options` | 地區、縣市、類別、優惠類型清單 | |
| GET | `/api/events` | 搜尋。參數：`region`、`city_id`、`date_from`、`date_to`（yyyy-mm-dd）、`category_id`、`discount_type_id`（可多個）、`keyword` | |
| GET | `/api/events/{id}` | 活動詳情，含場次（附 Google 地圖連結）與優惠 | |
| POST | `/api/auth/register` | 註冊 `{name, email, password, default_city_id}`，密碼至少 8 碼 | |
| POST | `/api/auth/login` | 登入 `{email, password}`，回傳 token | |
| GET | `/api/me` | 目前登入的使用者 | ✓ |
| GET | `/api/saves` | 我的收藏 | ✓ |
| POST | `/api/saves/{event_id}` | 收藏（重複收藏回傳 409） | ✓ |
| DELETE | `/api/saves/{event_id}` | 取消收藏 | ✓ |

需登入的 API：在請求標頭加上 `Authorization: Bearer <登入拿到的 token>`。寫法可參考 `web/app.js` 的 `api()` 函式。

## 安全性說明

- 密碼以 PBKDF2-SHA256 加上隨機 salt 雜湊後才存入資料庫，資料庫裡沒有原始密碼。
- SQL 一律使用參數（`?`／`[@名稱]`），不把使用者輸入直接拼進 SQL，避免 SQL injection。
- 測試資料一律使用假名與 `example.com` 信箱。
