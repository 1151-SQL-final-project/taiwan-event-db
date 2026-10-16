# taiwan-event-db

SQL與資料庫設計 115-1 期末專題：臺灣活動資訊管理系統

「臺灣活動彙整搜索App」的後台資料庫：整合各地區、各類型活動，由**商家上架**活動與優惠、**管理員審核**後公開，
讓**使用者**依地區、時間、活動類型、優惠類型四個條件快速查詢，並特別標出學生優惠、早鳥優惠。

```
網頁 (web/)  ⇄  後端 Python FastAPI (api/)  ⇄  Access 資料庫 (db/)
                       ↑ 讀取 sql/ 裡的查詢檔、檢查角色權限
```

資料庫共 **8 張資料表**：活動類型、縣市、場館、活動、優惠類型、活動優惠、使用者、收藏紀錄。
設計說明與審核流程見 [docs/schema.md](docs/schema.md)（10/12 的場次表提案 `schema-v2.md` 沒有採用）。

## 三種角色

| 角色 | 能做的事 | 目前進度 |
|---|---|---|
| 使用者 | 依地區／縣市、日期、類別（可一次選「學習類」）、優惠類型查詢；收藏 | ✅ 後端與測試網頁可用 |
| 商家 | 上架活動與優惠、修改自己的活動、新增場館；新增或修改後一律「待審核」 | ⏳ API 路徑已定（回傳 501），等 SQL 與頁面 |
| 管理員 | 審核（通過／退回）、違規下架、重新上架、統計 | ⏳ API 路徑已定（回傳 501），等 SQL 與頁面 |

- 註冊時可以選「使用者」或「商家」；**管理員帳號不開放註冊**，由程式建立。
- Access 沒有使用者權限分級，角色權限由後端檢查（`api/main.py` 的 `require_role`）。
- 查詢只顯示「上架中」而且還沒結束的活動；已結束的活動要用 UPDATE 自動改成「已下架」（⏳ 待實作，見 [sql/README.md](sql/README.md)）。

## 資料夾

| 資料夾 | 內容 | 負責 |
|---|---|---|
| `db/` | `schema.py` 8 張表的結構（驗證規則、查閱欄位、關聯）；`build_test_db.py` 產生測試用資料庫；正式 Access 主檔之後放這裡 | 晏均（主檔） |
| `api/` | 後端：連接 Access、登入（含角色）、搜尋、收藏；商家與管理員 API 的骨架 | 晨嬡 |
| `sql/` | 每個查詢一個 `.sql` 檔，後端直接讀取（寫法與「還沒寫的查詢」見 [sql/README.md](sql/README.md)） | 伯元 |
| `web/` | 網頁。目前是沒有設計的串接測試版，功能都能用（見 [web/README.md](web/README.md)） | 邦妤（使用者頁面）、昱妏（商家、管理員頁面） |
| `data/` | 整理好的 CSV 資料；`data/templates/` 是建檔範本（見 [說明](data/templates/README.md)） | 俊緯、揚健 |
| `docs/` | 提案、報告、會議紀錄、引用清單；資料表設計見 [docs/schema.md](docs/schema.md) | 全組 |

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

測試帳號（密碼都是 `test1234`）：

| 角色 | 信箱 |
|---|---|
| 使用者 | `student@example.com` |
| 商家 | `merchant@example.com` |
| 管理員 | `admin@example.com` |

測試資料有 12 場「（測試）」活動，涵蓋四種審核狀態（待審核、上架中、已退回、已下架）與已結束的活動。

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

需登入的 API：在請求標頭加上 `Authorization: Bearer <登入拿到的 token>`。寫法可參考 `web/app.js` 的 `api()` 函式。
角色不對時回傳 403；標「⏳」的還沒實作，目前回傳 501，但路徑、參數、權限已經定好，網頁可以先照這個格式做畫面。

| 方法 | 路徑 | 說明 | 角色 |
|---|---|---|---|
| GET | `/api/health` | 串接測試：從 Access 查 1 筆活動 | |
| GET | `/api/options` | 地區、類別分組、審核狀態、縣市、類別、優惠類型清單 | |
| GET | `/api/events` | 搜尋上架中、還沒結束的活動。參數：`region`、`city_id`、`date_from`、`date_to`（yyyy-mm-dd）、`category_id`、`category_group`（學習類／休閒類）、`discount_type_id`（可多個）、`keyword` | |
| GET | `/api/events/{id}` | 活動詳情：場館地址（附 Google 地圖連結）、優惠、上架商家。非上架中的活動只有上架的商家和管理員看得到 | |
| POST | `/api/auth/register` | 註冊 `{name, email, password, role, default_city_id}`，`role` 只能是「使用者」或「商家」，密碼至少 8 碼 | |
| POST | `/api/auth/login` | 登入 `{email, password}`，回傳 token 與角色 | |
| GET | `/api/me` | 目前登入的帳號（含角色 `UserRole`） | 登入 |
| GET | `/api/saves` | 我的收藏 | 使用者 |
| POST | `/api/saves/{event_id}` | 收藏（只能收藏上架中的活動；重複收藏回傳 409） | 使用者 |
| DELETE | `/api/saves/{event_id}` | 取消收藏 | 使用者 |
| GET | `/api/venues` | ⏳ 場館清單 | 商家、管理員 |
| POST | `/api/venues` | ⏳ 新增場館 `{name, city_id, address}` | 商家、管理員 |
| GET | `/api/merchant/events` | ⏳ 我上架的所有活動 | 商家 |
| POST | `/api/merchant/events` | ⏳ 上架活動 `{title, category_id, venue_id, start_date, end_date, price, url, description, discounts: [{discount_type_id, price, description, start_date, end_date}]}` → 待審核 | 商家 |
| PUT | `/api/merchant/events/{id}` | ⏳ 修改自己的活動與優惠（同上格式）→ 回到待審核 | 商家 |
| GET | `/api/admin/events` | ⏳ 所有活動，參數 `status`、`keyword` | 管理員 |
| POST | `/api/admin/events/{id}/status` | ⏳ `{status}`：通過、退回、違規下架、重新上架 | 管理員 |
| GET | `/api/admin/stats` | ⏳ 各審核狀態活動數、各地區上架數、熱門收藏排行 | 管理員 |

## 安全性說明

- 密碼以 PBKDF2-SHA256 加上隨機 salt 雜湊後才存入資料庫，資料庫裡沒有原始密碼。
- SQL 一律使用參數（`?`／`[@名稱]`），不把使用者輸入直接拼進 SQL，避免 SQL injection。
- 角色權限由後端檢查；管理員不開放註冊。
- 測試資料一律使用假名與 `example.com` 信箱。
