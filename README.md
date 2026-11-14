# taiwan-event-db

SQL與資料庫設計 115-1 期末專題：**探點**（臺灣活動資訊管理系統）

「探點」活動查詢網站的後台資料庫：整合各地區、各類型活動，由**商家上架**活動與優惠、**管理員審核**後公開，
讓**使用者**依地區、時間、活動類型、優惠類型四個條件快速查詢，並特別標出學生優惠、早鳥優惠。

```
文化部開放資料 ─ etl/fetch_moc.py ─▶ data/raw/ ─ etl/clean_moc.py ─▶ data/clean/ ─┐
人工建檔（優惠、活動）─────────────────────────────────▶ data/manual/ ─┴─ db/build_db.py ─▶ db/events.accdb

網頁 (web/)  ⇄  後端 Python FastAPI (api/，讀取 sql/ 裡的查詢檔、檢查角色權限)  ⇄  db/events.accdb
Access 表單管理後台 (db/後台.accdb，見 docs/access-form-guide.md)  ⇄  db/events.accdb
```

資料庫共 **8 張資料表**（設計說明見 [docs/schema.md](docs/schema.md)）：
活動類型、縣市、場館、活動、優惠類型、活動優惠、使用者、收藏紀錄。

目前資料量：活動 1,229 筆、場館 412 個（文化部開放資料，2026/11/02 下載；同一場活動在多個場館舉辦時，每個場館各一筆）。
其中約 810 筆在 OPENTIX 售票，票價與優惠（學生、早鳥、敬老、團體）改用 OPENTIX 活動頁上的結構化資料：
有票價的活動約 76%，優惠 1,064 筆（早鳥 89 筆）。其餘從開放資料文字擷取的優惠，核對結果見 `data/review/discount_verification.csv`。

## 三種角色

| 角色 | 網頁上能做的事 | 示範帳號（密碼都是 `test1234`） |
|---|---|---|
| 使用者 | 依地區／縣市、日期、類別（可一次選「學習類」）、優惠類型查詢；活動狀態可選進行中、即將開始／開賣、早鳥即將截止；看「即將開賣」區塊；收藏、優惠截止與開賣提醒 | `student@example.com` |
| 商家 | 商家後台（以上架為主）：上架活動（含多筆優惠、開賣時間、活動圖片〔上傳檔案或貼網址〕，可從過去的活動帶入日期以外的資料）、修改自己的活動、新增場館、看被退回的理由與各狀態場數；活動用和找活動一樣的卡片呈現（含各自的收藏數），被退回的另外一列列出理由；選場館和日期時列出同場館同期間的活動，送出前若系統裡已有相似的活動會先提醒。新增或修改後一律「待審核」。選單只有商家後台、上架新活動、找活動 | `merchant@example.com` |
| 管理員 | 管理員後台（以審核為主）：「待審核」左邊是佇列（標出疑似重複、快開始的活動），右邊直接顯示審核要看的官網、票價、優惠、介紹、重複提醒與上架者過去的紀錄，通過或退回（彈窗勾選理由）後自動跳下一場；「活動管理」搜尋所有活動做違規下架、重新上架。選單是首頁、管理員後台、找活動、數據 | `admin@example.com` |

- 註冊時可以選「使用者」或「商家」；**管理員帳號不開放註冊**，由 `build_db.py` 建立。
- Access 沒有使用者權限分級，角色權限由後端檢查（`api/common.py` 的 `require_role`）。
- **自動下架**：查詢只顯示「上架中」而且還沒結束的活動；伺服器啟動、打開商家或管理員後台時，
  會用 UPDATE 把已結束的活動改成「已下架」（Access 沒有排程，所以這樣做）。
- 開放資料、人工建檔的活動沒有商家，一律掛在管理員帳號下，`EventDataSource` 記錄出處。
- 另有 20 個 `demoNN@example.com` 假帳號，用來產生收藏排行的資料。
- **開賣時間**（`EventSaleStartDate`）：熱門演唱會常常一開賣就賣完，所以除了活動日期，也記錄售票平台開放購票的時間。
  OPENTIX 的活動取自活動頁的結構化資料（約 760 筆），商家上架時可以自己填；找活動頁有「即將開賣」區塊，活動狀態可選「即將開始／開賣」，
  收藏的活動快開賣時，「我的收藏」會提醒。
- **退回理由**（`EventRejectReason`）：管理員退回時一定要勾選理由（可加補充說明），商家在後台看得到；商家修改送審後清空。
- **重複上架提醒**：待審核的活動會和日期重疊的已上架、待審核活動比對名稱相似度（去掉空白、標點後比相鄰兩字）、
  場館與縣市，像的話在審核清單顯示「很可能重複／可能重複」並列出是哪幾場；這時「通過並上架」要按兩次，
  按「退回」會預先勾「重複上架」。商家按「送出審核」前也會先比對一次（只列已上架和自己的活動），可以回去修改或仍要送出。候選活動用 `sql/admin/similar_events.sql` 撈，相似度在 `api/similar.py` 計算（Access SQL 沒有模糊比對）。

## 資料夾

| 資料夾 | 內容 | 負責 |
|---|---|---|
| `db/` | `schema.py` 資料表結構；`build_db.py` 從 CSV 產生正式資料庫；`build_test_db.py` 產生少量測試資料；`build_admin_frontend.py` 產生 Access 管理後台 | 晏均（主檔） |
| `etl/` | 下載、清理文化部開放資料；匯出 Google 試算表用的資料 | 俊緯 |
| `api/` | 後端：連接 Access、登入、角色權限、搜尋、收藏、商家上架、管理員審核 | 晨嬡 |
| `sql/` | 每個查詢一個 `.sql` 檔，後端直接讀取（`merchant/` 商家、`admin/` 管理員；寫法見 [sql/README.md](sql/README.md)） | 伯元 |
| `web/` | 網頁：搜尋、活動詳情、收藏與提醒、數據圖表、登入註冊（使用者頁面：邦妤）；商家後台、管理員後台（昱妏） | 邦妤、昱妏 |
| `data/clean/` | 清理後的開放資料 CSV（程式產生，不要手動改） | 俊緯 |
| `data/manual/` | 人工建檔的 CSV，格式見 [data/templates/README.md](data/templates/README.md) | 揚健、俊緯 |
| `data/review/` | 清理報告 `etl_report.md`、被捨棄的資料、待人工確認的優惠、匯入錯誤 | 俊緯、揚健 |
| `data/sheets/` | Google Sheet Query 用的攤平資料 | |
| `docs/` | [系統建置與操作手冊](docs/setup-guide.md)、[資料表設計（8 張表）](docs/schema.md)、[Access 表單製作步驟](docs/access-form-guide.md)、[Google Sheet Query](docs/google-sheet-query.md) | 全組 |
| `tests/` | 自動測試：API 角色權限、網頁端對端、Access 後台 | |

## 第一次在自己電腦上執行

> 給老師或第一次接觸的人：圖文步驟、測試帳號、Demo 流程與常見問題見 **[系統建置與操作手冊](docs/setup-guide.md)**。

需要：Windows、Microsoft Office（含 Access）、[Python 3.12](https://www.python.org/downloads/)（安裝時勾選「Add python.exe to PATH」）。

**Office 和 Python 的位元數要一樣**（現在的 Office 幾乎都是 64 位元，Python 也裝 64 位元的就對了）。檢查方法：

```powershell
python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
```

**一鍵啟動（Demo 用）**：雙擊專案資料夾裡的 `啟動探點.bat`。第一次會自動建立虛擬環境、安裝套件、產生資料庫（約 2–3 分鐘，需要網路），之後每次約 10 秒就會自動打開瀏覽器；關掉黑色視窗就停止網站。雙擊 `建立桌面捷徑.bat` 可以在桌面放一個「探點」捷徑。程式在 `tools\start.py`。

要自己下指令的話，在專案資料夾開啟 PowerShell（VS Code：終端機 → 新增終端機），依序執行：

```powershell
# 1. 建立虛擬環境並安裝套件（只要做一次）
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 2. 產生資料庫 db\events.accdb（data\clean 已經有清理好的資料，可以直接跑）
#    開放資料＋示範帳號與示範商家的活動；「（測試）」活動只放在自動測試自己建的資料庫（tests\test_db.py）
.venv\Scripts\python db\build_db.py

# 3. 啟動後端
.venv\Scripts\python -m uvicorn main:app --app-dir api --reload
```

看到 `Uvicorn running on http://127.0.0.1:8000` 就成功了：

- 網頁：<http://127.0.0.1:8000>
- API 測試頁（可以直接在瀏覽器試每一支 API）：<http://127.0.0.1:8000/docs>

停止後端：在 PowerShell 按 `Ctrl + C`。

### 建議的 Demo 流程（約 4 分鐘）

1. **使用者** `student@example.com` 登入 → 首頁看「本週學生優惠」「這週末」→ 找活動按「學生優惠」，再選地區「北部」、類型「學習類」→ 點一場活動 →「在 Google 地圖開啟」→ 收藏 →「我的收藏」看優惠截止提醒與開賣提醒。
2. **商家** `merchant@example.com` 登入 → 商家後台 →「上架新活動」：選場館（或當場新增場館）、加一筆學生優惠和一筆早鳥優惠（故意不填早鳥截止日，展示驗證規則）→ 送出後是「待審核」，搜尋不到。
3. **管理員** `admin@example.com` 登入 → 管理員後台「待審核」→ 在左邊佇列點剛才的活動，右邊確認資料後按「通過並上架」（和已上架活動相似時會出現重複提醒，按「退回…」可選理由）→ 切到「活動管理」搜尋活動、違規下架。
4. 回到「找活動」，剛才的活動已經查得到；管理員再按「違規下架」→ 又查不到了。

### 線上示範版（簡報用連結）

<https://1151-sql-final-project.github.io/>：不需要 Python、Access 的示範版。網頁和 `web/` 完全一樣，只多載入 `demo/mock-api.js`，
在瀏覽器裡照 `sql/` 的查詢模擬後端 API，資料是從 `db/events.accdb` 匯出的快照（`data.js`）。
「（測試）」活動的日期會依打開的日期往後推，所以隨時打開都看得到即將開賣、早鳥即將截止的範例。
示範時新增、修改的資料只存在看的人自己的瀏覽器，頁尾「重設示範資料」可以清掉。

資料庫或網頁更新後重新產生（輸出到 `demo/site/`，再推到組織的 `1151-SQL-final-project.github.io` repo）：

```powershell
.venv\Scripts\python demo\build_demo.py
```

### 更新開放資料

```powershell
.venv\Scripts\python etl\fetch_moc.py     # 下載最新資料到 data\raw（約 1 分鐘）
.venv\Scripts\python etl\clean_moc.py     # 清理（一場活動多個場館時依場館拆成多筆），結果與報告在 data\clean、data\review
.venv\Scripts\python etl\fetch_opentix.py  # 下載 OPENTIX 活動頁（約 13 分鐘，每秒 1 頁）
.venv\Scripts\python etl\clean_opentix.py  # 從 OPENTIX 取票價與學生、早鳥、敬老、團體優惠
.venv\Scripts\python etl\verify_discounts.py # 到官網核對其餘自動擷取的優惠
.venv\Scripts\python db\build_db.py
.venv\Scripts\python etl\export_sheets.py # （選用）更新 Google 試算表用的資料
```

`data/review/etl_report.md` 會列出每條清理規則處理了幾筆（例如「依行政區推定縣市 18 筆」「在多個場館舉辦，依場館拆成多筆 100 筆」），期末報告可直接引用。

### 改接其他資料庫

預設連 `db/events.accdb`；還沒產生時改連 `db/test_events.accdb`（`db\build_test_db.py` 產生的少量測試資料）。要改接其他 Access 檔，啟動前設定環境變數：

```powershell
$env:EVENT_DB_PATH = "C:\完整路徑\活動資料庫.accdb"
.venv\Scripts\python -m uvicorn main:app --app-dir api --reload
```

### 自動測試

```powershell
.venv\Scripts\python tests\api_roles.py              # API：三種角色權限、上架 → 審核（含退回理由）→ 收藏 → 下架、開賣時間、重複提醒（98 項）
.venv\Scripts\python tests\e2e_web.py                # 網頁：用 Edge 實際操作（145 項，含商家上架、示範帳號一鍵登入、退回彈窗、重複提醒、即將開賣）
.venv\Scripts\python db\build_admin_frontend.py      # 產生 Access 管理後台
.venv\Scripts\python tests\verify_access_frontend.py # Access 後台（18 項）
```

每個測試會先自己建一個加了「（測試）」活動的資料庫（約 1 分鐘，`tests/test_db.py`），不會改到 `db/events.accdb`。

### 常見問題

| 狀況 | 解決方法 |
|---|---|
| `找不到資料庫檔案` | 還沒執行第 2 步，或 `EVENT_DB_PATH` 路徑打錯 |
| `Data source name not found` / `IM002` | Office 和 Python 位元數不同，或沒裝 Access。可另外安裝 [Microsoft Access Database Engine](https://www.microsoft.com/en-us/download/details.aspx?id=54920)（選和 Python 相同位元數的版本） |
| `build_db.py`／`build_test_db.py` 刪不掉舊檔 | 資料庫正在 Access 裡開著（或後端正在跑），先關掉 |
| 網頁顯示舊的內容 | 按 `Ctrl + F5` 強制重新整理 |

## API 一覽

需登入的 API：在請求標頭加上 `Authorization: Bearer <登入拿到的 token>`。寫法可參考 `web/js/core.js` 的 `api()` 函式。
角色不對時回傳 403。

| 方法 | 路徑 | 說明 | 角色 |
|---|---|---|---|
| GET | `/api/health` | 串接測試：從 Access 查 1 筆活動 | |
| GET | `/api/options` | 地區、類別分組、審核狀態、退回理由選項、縣市、類別、優惠類型清單 | |
| GET | `/api/events` | 搜尋上架中、還沒結束的活動。參數：`region`、`city_id`、`date_from`、`date_to`（yyyy-mm-dd）、`category_id`、`category_group`（學習類／休閒類）、`discount_type_id`（可多個）、`keyword`、`free_only`、`phase`（活動狀態：ongoing 進行中／upcoming 即將開始或開賣／early_bird 早鳥即將截止）、`sort`（date／price／ending／sale）、`page`、`page_size`。回傳 `{total, page, page_size, items}` | |
| GET | `/api/events/{id}` | 活動詳情：場館地址與 Google 地圖連結（`GoogleMapsURL` 用場館名稱查，直接開到場館；`GoogleMapsAddressURL` 用地址定位，當備用）、優惠、上架商家。非上架中的活動只有上架的商家和管理員看得到 | |
| GET | `/api/stats` | 各類別上架中的活動數（加總是上架總數），熱門收藏排行 | |
| GET | `/api/discounts/early-bird?days=14` | N 天內截止的早鳥優惠 | |
| GET | `/api/sales/upcoming?days=14` | N 天內開賣的活動（依開賣時間排序） | |
| POST | `/api/auth/register` | 註冊 `{name, email, password, role}`，`name` 是暱稱（商家填商家名稱），`role` 只能是「使用者」或「商家」，密碼至少 8 碼 | |
| POST | `/api/auth/login` | 登入 `{email, password}`，回傳 token 與角色 | |
| GET | `/api/me` | 目前登入的帳號（含角色） | 登入 |
| PUT | `/api/me` | 修改名稱 `{name}`（暱稱／商家名稱，最多 20 字） | 登入 |
| GET | `/api/saves` | 我的收藏 | 使用者 |
| GET | `/api/saves/reminders?days=7` | 我收藏的活動中，N 天內截止的優惠 | 使用者 |
| GET | `/api/saves/sale-reminders?days=14` | 我收藏的活動中，N 天內開賣的 | 使用者 |
| POST | `/api/saves/{event_id}` | 收藏（只能收藏上架中的活動；重複收藏回傳 409） | 使用者 |
| DELETE | `/api/saves/{event_id}` | 取消收藏 | 使用者 |
| GET | `/api/venues` | 場館清單 | 商家、管理員 |
| POST | `/api/venues` | 新增場館 `{name, city_id, address}` | 商家、管理員 |
| POST | `/api/merchant/events/similar` | 送出前檢查相似活動 `{title, venue_id, start_date, end_date, url, event_id}`（修改時填 `event_id` 排除自己）；只回傳已上架的和自己的活動 | 商家 |
| GET | `/api/merchant/events` | 我上架的所有活動（各種審核狀態） | 商家 |
| POST | `/api/merchant/images` | 上傳活動圖片：請求內容直接是圖片檔（`Content-Type` 填 `image/jpeg`、`image/png`、`image/webp` 或 `image/gif`，5 MB 以內，會檢查檔案內容），存到 `web/uploads/`，回傳 `{url: "uploads/檔名"}` 放進 `image_url` | 商家 |
| POST | `/api/merchant/events` | 上架活動 `{title, category_id, venue_id, start_date, end_date, price, url, description, sale_start, image_url, discounts: [{discount_type_id, price, description, start_date, end_date}]}` → 待審核 | 商家 |
| PUT | `/api/merchant/events/{id}` | 修改自己的活動與優惠（同上格式）→ 回到待審核 | 商家 |
| GET | `/api/admin/events` | 所有活動，參數 `status`、`keyword`、`page`、`page_size`；回傳各狀態筆數與這次自動下架的筆數 | 管理員 |
| POST | `/api/admin/events/{id}/status` | `{status, reason}`：待審核 → 上架中（通過）／已退回（退回，`reason` 必填）；上架中 → 已下架（違規下架）；已下架 → 上架中（重新上架，已結束的不行） | 管理員 |
| GET | `/api/admin/events/{id}/similar` | 可能重複的活動（名稱相似、日期重疊，加上同場館或同縣市），最多 5 筆。`/api/admin/events` 的待審核活動也會附上 `Similar` | 管理員 |
| GET | `/api/admin/events/{id}/review` | 審核畫面要的資料：活動詳情（含優惠）、可能重複的活動、上架者其他活動各審核狀態的場數 | 管理員 |

## 安全性說明

- 密碼以 PBKDF2-SHA256 加上隨機 salt 雜湊後才存入資料庫，資料庫裡沒有原始密碼。
- SQL 一律使用參數（`?`／`[@名稱]`），不把使用者輸入直接拼進 SQL，避免 SQL injection。
- 商家只能修改自己的活動：UPDATE 的 WHERE 同時比對活動編號與商家編號。
- 商家新增或修改的活動一律「待審核」，管理員通過後才公開。
- 測試資料一律使用假名與 `example.com` 信箱。

## 資料來源與授權

- 活動資料：文化部「全國藝文活動資訊系統」開放資料，<https://opendata.culture.tw/>，依「政府資料開放授權條款－第1版」使用。每筆活動的 `EventDataSource` 欄位記錄來源。
- 自動擷取的優惠（`RecordedBy` 為「ETL自動擷取（待確認）」）是程式從活動的優惠說明文字解析出來的，可能有誤，正式使用前請逐筆到官網核對。
- 示範帳號、示範商家上架的活動、收藏紀錄都是假資料（`db/demo_events.py`）；標題有「（測試）」的活動只存在自動測試建的資料庫裡，`db/events.accdb` 沒有。
