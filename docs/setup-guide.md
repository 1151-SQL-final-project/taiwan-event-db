# 探點｜系統建置與操作手冊

SQL與資料庫設計 115-1 第二組期末專題 · 2026-10-17

## 1. 系統簡介與需要的環境

照這份手冊，約 20 分鐘可以在一台 Windows 電腦上把整個系統跑起來：下載專題、執行 3 個指令，就能用瀏覽器以使用者、商家、管理員三種身分操作。

系統由三部分組成，全部在同一台電腦上執行：

- **網頁**（`web/`）：瀏覽器打開 http://127.0.0.1:8000 操作。
- **後端**（`api/`）：Python FastAPI 程式，負責網頁和資料庫之間的資料傳遞，並檢查角色權限。
- **資料庫**（`db/events.accdb`）：Microsoft Access，共 8 張資料表；資料來自文化部開放資料與人工建檔，由程式自動建立。

執行前請確認電腦符合下表：

| 項目 | 需求 | 備註 |
| --- | --- | --- |
| 作業系統 | Windows 10 或 11 | Access 只能在 Windows 執行，Mac 無法使用 |
| Microsoft Access | Office 內含的 Access（2016 以後），或免費的 [Microsoft Access Database Engine 2016](https://www.microsoft.com/en-us/download/details.aspx?id=54920) | 只需要資料庫元件；要在 Access 裡看資料表與表單才需要完整的 Access |
| Python | [3.12](https://www.python.org/downloads/)（3.10 以上可用） | 安裝時勾選「Add python.exe to PATH」 |
| 位元數 | **Python 與 Office 必須同為 64 位元（或同為 32 位元）** | 不一致會連不上資料庫；現在的 Office 幾乎都是 64 位元 |
| 網路 | 第一次安裝 Python 套件時需要 | 之後可離線執行 |
| 瀏覽器 | Edge 或 Chrome | 自動測試會用到電腦上的 Edge |

## 2. 取得專題檔案

請向組長（王晨嬡）索取專題的 **ZIP 壓縮檔**，解壓縮到一個**沒有中文或空格的路徑更保險**，例如 `C:\taiwan-event-db-full`。

程式放在組員使用的私人 GitHub 儲存庫，沒有受邀的帳號打不開，所以不用另外到 GitHub 下載；ZIP 裡的內容和儲存庫相同。

解壓後的資料夾裡應該看得到 `api`、`db`、`sql`、`web`、`README.md`、`requirements.txt` 等檔案。下文稱這個資料夾為「**專題資料夾**」。

資料庫檔案（`.accdb`）不在 ZIP 裡，會在下一節由程式從已整理好的 CSV 自動產生，不需要另外下載。

## 3. 安裝與第一次啟動

### 最簡單的方式：雙擊「啟動探點.bat」

確認電腦已安裝第 1 節的 Python 與 Access 元件後，雙擊專題資料夾裡的 **`啟動探點.bat`**，會跳出一個黑色視窗並自動完成下面的步驟 2–4：

- **第一次執行**：建立虛擬環境、安裝套件（需要網路），再產生資料庫，總共約 2–3 分鐘。
- **之後每次**：約 10 秒，網站準備好就會自動用瀏覽器打開 <http://127.0.0.1:8000>。
- **Demo 期間不要關掉黑色視窗**；關掉視窗就會停止網站。重複雙擊時，如果網站已經在執行，只會再打開一次瀏覽器。
- 想在桌面放捷徑：雙擊 **`建立桌面捷徑.bat`**，桌面會出現「探點」圖示。專題資料夾搬到別的地方後，要重新建立一次。

出現 ✗ 時，箭頭後面會寫解決方法（常見的是沒有網路、Python 與 Office 位元數不同、找不到 Access 驅動程式）；也可以照下面步驟 1 檢查環境。

### 自己輸入指令

以下指令都在**專題資料夾**裡的 PowerShell 執行：在檔案總管打開專題資料夾，點上方網址列輸入 `powershell` 按 Enter 即可。步驟 2、3 只需要做一次。

**步驟 1：檢查環境**（約 10 秒）

```powershell
python tools\check_env.py
```

每一項應該是 ✓；出現 ✗ 時，箭頭後面會寫解決方法（最常見的是 Python 與 Office 位元數不同）。這時還沒裝套件，「套件」「資料庫」兩項顯示未安裝是正常的。

**步驟 2：建立虛擬環境並安裝套件**（約 1–2 分鐘，需要網路）

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

虛擬環境會建在專題資料夾裡的 `.venv`，不會影響電腦上其他的 Python 程式。

**步驟 3：產生資料庫**（約 1 分鐘）

```powershell
.venv\Scripts\python db\build_db.py
```

完成後會印出各資料表的筆數（活動約 1,230 筆），並建立 `db\events.accdb`，裡面是開放資料，加上示範帳號、示範收藏與示範商家上架的活動（有即將開賣、早鳥即將截止、待審核、已退回等情境，方便 Demo）。想把資料重置回初始狀態時，再跑一次這個指令即可。

**步驟 4：啟動網站**（每次使用都要做）

```powershell
.venv\Scripts\python -m uvicorn main:app --app-dir api
```

看到 `Uvicorn running on http://127.0.0.1:8000` 就成功了，用瀏覽器打開：

- 網站：<http://127.0.0.1:8000>
- API 測試頁（可以直接試每一支 API）：<http://127.0.0.1:8000/docs>

使用期間請不要關掉 PowerShell 視窗；要停止網站，在該視窗按 `Ctrl + C`。

## 4. 測試帳號與建議操作流程

三種角色各有一個測試帳號，密碼都是 `test1234`；在網站右上角「登入」輸入即可。帳號與信箱都是假資料。

| 角色 | 信箱 | 登入後能做的事 |
| --- | --- | --- |
| 使用者 | `student@example.com` | 查詢活動、收藏、看優惠截止與開賣提醒 |
| 商家 | `merchant@example.com` | 商家後台：上架（可從過去的活動帶入資料）、修改自己的活動，新增場館，看各狀態場數與每場活動的收藏數 |
| 管理員 | `admin@example.com` | 管理員後台：審核（左邊佇列、右邊審核資料，處理完自動跳下一場）、活動管理（搜尋、違規下架、重新上架） |

也可以自己註冊新帳號（選「使用者」或「商家」）；管理員帳號不開放註冊。

建議依下列順序操作一次（約 5 分鐘），就能看到「商家上架 → 管理員審核 → 使用者查得到」的完整流程：

1. **使用者查詢**：不登入也能查。在「找活動」選地區「北部」、類型「學習類」、優惠「學生優惠」，點一場活動看詳情與「在 Google 地圖開啟」。
2. **收藏**：用 `student@example.com` 登入，在活動頁按「收藏活動」，到「我的收藏」看優惠即將截止與即將開賣的提醒（找活動頁上方的「即將開賣」區塊列出 14 天內開賣的場次）。
3. **商家上架**：在「登入」頁登出，改用 `merchant@example.com` 登入 →「上架新活動」→ 填寫資料、選場館（也可以當場新增）、加一筆優惠 →「送出審核」。活動顯示「待審核」，這時搜尋不到。
    - 可以故意加一筆「早鳥優惠」但不填截止日期，會看到 Access 資料表驗證規則擋下的中文訊息。
    - 活動名稱和日期填得跟某場已上架的活動很像（同場館、日期重疊），送出時會先提醒「系統裡已經有相似的活動」。
4. **管理員審核**：登出後用 `admin@example.com` 登入 →「待審核」分頁 → 對剛才的活動按「通過並上架」；和已上架活動相似時，下方會出現「很可能重複」或「可能重複」提醒，按「退回…」可以選退回理由，商家登入後在「已退回」分頁看得到。切到「統計」可看各審核狀態、各地區活動數與熱門收藏排行。
5. **確認結果**：回到「找活動」搜尋剛才的活動名稱，已經查得到。管理員在「上架中」分頁按「違規下架」（要按第二次確認）後，就又查不到了。

已結束的活動會**自動下架**：啟動網站或打開商家、管理員後台時，系統會把結束日期已過的活動改為「已下架」，管理員後台會跳出下架筆數。

## 5. 在 Access 裡檢視資料庫

用 Access 直接打開 `db\events.accdb` 就能看到所有資料表、關聯與查詢；網站開著的時候也可以打開，兩邊用的是同一份資料。

| 想看的內容 | 在 Access 裡怎麼找 |
| --- | --- |
| 8 張資料表與資料 | 左側「資料表」：`CategoryTable`、`CityTable`、`VenueTable`、`EventTable`、`DiscountTypeTable`、`DiscountTable`、`UserTable`、`SaveTable` |
| 欄位型態、驗證規則、查閱欄位 | 在資料表上按右鍵 →「設計檢視」 |
| 資料表關聯（ER） | 「資料庫工具」→「資料庫關聯圖」（第一次打開可按「所有關聯」顯示全部） |
| 系統用到的 SQL（共 37 個） | 左側「查詢」：`查_`（使用者）、`商家_`、`管理_`、`統計_`、`提醒_` 開頭。雙擊即可執行，有參數的會跳出「請輸入 …」的輸入框 |

例如雙擊 `統計_熱門收藏排行` 會執行 JOIN＋GROUP BY＋TOP 10；右鍵 →「SQL 檢視」可以看到 SQL 本身。同樣的 SQL 也放在專題資料夾的 `sql\` 裡，一個查詢一個檔案。

**選用：Access 表單管理後台**。另有一個用 Access 表單做的管理後台（主選單、活動管理含優惠子表單、一鍵下架），要先用程式產生：

```powershell
.venv\Scripts\python db\build_admin_frontend.py
```

產生的是 `db\後台.accdb`，打開會先顯示主選單。執行前請先關閉 Access，程式執行時會短暫在背景開啟 Access。

這支程式會把專題的 `db\` 資料夾加入 Access 的「信任位置」（只限目前的 Windows 使用者），主選單的 VBA 按鈕才能直接使用。不希望更改設定時，改用：

```powershell
.venv\Scripts\python db\build_admin_frontend.py --no-trust
```

之後打開 `後台.accdb` 時，黃色安全性提示列按「啟用內容」即可。商家上架與審核以網站為主，Access 後台是給管理員直接維護資料用的。

## 6. 選用功能

以下都不是執行系統的必要步驟，供想進一步檢查時使用。請先用 `Ctrl + C` 停止網站再執行。

**自動測試**：都在資料庫的複本上測，不會改到 `events.accdb`；全部通過時最後會印出「全部通過」。

| 指令 | 測什麼 | 項目數 | 時間 |
| --- | --- | --- | --- |
| `.venv\Scripts\python tests\api_roles.py` | 後端：三種角色的權限，上架 → 審核（含退回理由）→ 收藏 → 下架流程、開賣時間、重複提醒 | 63 | 約 1 分鐘 |
| `.venv\Scripts\python tests\e2e_web.py` | 網頁：用電腦上的 Edge 實際操作，含退回彈窗、重複提醒、即將開賣、手機寬度與深淺色 | 68 | 約 3 分鐘 |
| `.venv\Scripts\python tests\verify_access_frontend.py` | Access 後台（需先產生 `後台.accdb`）；測試時 Access 視窗會短暫出現 | 18 | 約 1 分鐘 |

**更新開放資料**：專題附的是 2026/11/02 下載、整理好的資料。要改用最新的文化部資料，依序執行（需要網路，全部約 15 分鐘）：

```powershell
.venv\Scripts\python etl\fetch_moc.py
.venv\Scripts\python etl\clean_moc.py
.venv\Scripts\python etl\fetch_opentix.py
.venv\Scripts\python etl\clean_opentix.py
.venv\Scripts\python db\build_db.py
```

每條清理規則處理了幾筆，會記在 `data\review\etl_report.md`。

**Google Sheet 版本**：把 `data\sheets\events_flat.csv` 匯入 Google 試算表，就能用 `QUERY()` 公式查詢同樣的資料，步驟與公式見 [docs/google-sheet-query.md](google-sheet-query.md)。

## 7. 常見問題

遇到問題時，先跑一次 `.venv\Scripts\python tools\check_env.py`，它會指出是哪一項環境不符。

| 狀況 | 原因 | 解決方法 |
| --- | --- | --- |
| `'python' 不是內部或外部命令` | 安裝 Python 時沒勾「Add python.exe to PATH」 | 重新執行安裝程式 →「Modify」勾選，或改用 `py` 代替 `python` |
| `Data source name not found` 或 `IM002` | Python 與 Office 位元數不同，或沒有 Access 元件 | 裝和 Office 同位元數的 Python；沒有 Access 則安裝同位元數的 Access Database Engine |
| 執行指令時顯示「執行指令碼已停用」 | PowerShell 的執行原則限制 | 本手冊的指令都直接呼叫 `.venv\Scripts\python`，不需要「啟用」虛擬環境；照手冊指令輸入即可 |
| 網頁顯示「找不到資料庫檔案」 | 還沒做第 3 節步驟 3 | 執行 `db\build_db.py` |
| `build_db.py` 說刪不掉舊檔、檔案正在使用 | `events.accdb` 正在 Access 裡開著，或網站還在執行 | 關掉 Access，在網站的 PowerShell 按 `Ctrl + C`，再重跑 |
| `address already in use` 或 8000 埠被佔用 | 已經有另一個網站在用 8000 埠 | 關掉另一個，或啟動時加 `--port 8001`，網址改成 http://127.0.0.1:8001 |
| 網頁顯示舊的內容 | 瀏覽器快取 | 按 `Ctrl + F5` 強制重新整理 |
| 登入後一段時間要重新登入 | 登入有效期限 7 天 | 重新登入即可 |
| Access 後台按鈕沒反應 | VBA 被停用（檔案不在信任位置） | 按黃色提示列的「啟用內容」 |

## 8. 檔案結構速查

| 資料夾或檔案 | 內容 |
| --- | --- |
| `README.md` | 專題說明、API 一覽（和本手冊的安裝步驟相同） |
| `docs\schema.md` | 8 張資料表的設計說明、審核流程、驗證規則 |
| `db\schema.py` | 建表程式：欄位型態、驗證規則、查閱欄位、關聯 |
| `db\build_db.py` | 從 CSV 產生 `events.accdb`，並建立測試帳號 |
| `sql\` | 系統用到的所有 SQL，一個查詢一個檔案；`merchant\` 商家、`admin\` 管理員 |
| `api\main.py` | 後端啟動入口，組合各功能的 API |
| `api\common.py` | 後端共用：角色權限檢查、常數 |
| `api\routes\` | 各功能的 API：活動查詢、登入、收藏、商家後台、管理員後台 |
| `web\` | 網頁（HTML、CSS、JavaScript） |
| `etl\` | 下載與清理文化部開放資料、OPENTIX 票價 |
| `data\clean\`、`data\review\` | 清理好的資料、清理報告與待人工確認的資料 |
| `tests\` | 自動測試 |
| `tools\check_env.py` | 環境檢查 |

活動資料來源：文化部「全國藝文活動資訊系統」[開放資料](https://opendata.culture.tw/)（政府資料開放授權條款—第 1 版）；測試帳號、收藏紀錄與示範商家上架的活動都是假資料。
