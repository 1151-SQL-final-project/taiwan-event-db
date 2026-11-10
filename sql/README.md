# sql

每個查詢一個 .sql 檔（伯元負責）。

檔名用英文，例如 `search_by_region.sql`，檔案開頭用一行註解說明這個查詢在做什麼。

**後端會直接讀這些檔案執行**，所以改了檔案、存檔，網頁重新整理就會用新的查詢（不用重開後端）。

## 寫法規則

1. **用 Access SQL 的語法**（JOIN 多張表要加括號、布林值寫 `True`、今天日期用 `Date()`、日期常數寫 `#2026/10/12#`）。
2. **參數寫成 `[@參數名稱]`**，例如 `WHERE e.EventID = [@event_id]`。
   - 貼到 Access 的 SQL 檢視執行時，Access 會跳出輸入框讓你填值，可以直接測。
   - 後端執行時會依名稱把值帶進去。**參數名稱要和後端用的一樣**（見下表），不要自己改名。
3. 開頭可以用 `--` 寫一兩行說明。**Access 的 SQL 檢視不認得 `--` 註解**，貼進 Access 測試時，只複製註解以下的部分。
4. 每個檔案只放一個 SQL 指令。
5. **文字一律用單引號**，例如 `WHERE t.DiscountTypeName = '早鳥優惠'`、`DateAdd('d', 7, Date())`。
   Access 的查詢視窗裡雙引號也能用，但後端透過 ODBC 執行時，雙引號會被當成參數，出現「參數太少」錯誤。
6. 執行 `db\build_db.py` 時，這裡每個檔案都會存成 Access 裡的「查詢」（例如 `統計_熱門收藏排行`），
   在 Access 左側直接雙擊就能執行，參數會變成「請輸入 幾天內」這類提示。名稱對照見 `db/build_db.py` 的 `QUERY_NAMES`。

## 後端目前用到的查詢

改這些檔案時，**欄位名稱（SELECT 出來的欄位）和參數名稱不要變**，網頁靠這些名稱顯示資料。
「上架中而且還沒結束」（`EventStatus = '上架中' AND EventEndDate >= Date()`）是「公開活動」的條件，查詢、統計都用它。

### 使用者（查詢、收藏）

| 檔案 | 用途 | 參數 |
|---|---|---|
| `list_categories.sql` | 類別下拉選單（含學習類／休閒類分組） | |
| `list_cities.sql` | 縣市下拉選單 | |
| `list_discount_types.sql` | 優惠類型勾選框 | |
| `search_events.sql` | 搜尋的基本查詢（活動＋類別＋場館＋縣市；篩選條件由後端接在後面） | |
| `event_detail.sql` | 活動詳情（含場館地址、上架商家、審核狀態） | `event_id` |
| `event_discounts.sql` | 活動的所有優惠與是否有效 | `event_id` |
| `user_by_email.sql` | 登入時找使用者 | `email` |
| `user_by_id.sql` | 目前登入的使用者（含角色） | `user_id` |
| `insert_user.sql` | 註冊 | `name`, `email`, `password_hash`, `role` |
| `update_user_name.sql` | 修改名稱（暱稱／商家名稱） | `name`, `user_id` |
| `list_saves.sql` | 我的收藏 | `user_id` |
| `insert_save.sql` | 收藏 | `user_id`, `event_id` |
| `delete_save.sql` | 取消收藏 | `user_id`, `event_id` |
| `stats_events_by_region.sql` | 各地區活動數（活動 → 場館 → 縣市 JOIN＋GROUP BY） | |
| `stats_events_by_city.sql` | 各縣市活動數 | |
| `stats_events_by_category.sql` | 各類別活動數、平均原價、免費活動數 | |
| `popular_saves.sql` | 熱門收藏排行前 10 名（JOIN＋GROUP BY＋TOP） | |
| `early_bird_ending_soon.sql` | N 天內截止的早鳥優惠 | `days` |
| `save_reminders.sql` | 我收藏的活動中，N 天內截止的優惠 | `user_id`, `days` |
| `sale_starting_soon.sql` | N 天內開賣的活動（比較 `Now()`，精確到時、分） | `days` |
| `save_sale_reminders.sql` | 我收藏的活動中，N 天內開賣的 | `user_id`, `days` |

### 商家後台（`merchant/`）與共用

| 檔案 | 用途 | 參數 |
|---|---|---|
| `merchant/list_my_events.sql` | 我上架的所有活動（各種審核狀態，含還沒截止的早鳥截止日） | `organizer_id` |
| `merchant/insert_event.sql` | 上架活動（INSERT，一律「待審核」） | `category_id`, `venue_id`, `title`, `start_date`, `end_date`, `price`, `url`, `organizer_id`, `description`, `sale_start`, `image_url` |
| `merchant/update_event.sql` | 修改自己的活動（UPDATE，改回「待審核」並清掉退回理由；WHERE 同時比對商家編號） | 同上＋`event_id` |
| `merchant/delete_event_discounts.sql` | 修改時先刪掉原本的優惠（DELETE） | `event_id` |
| `merchant/my_stats_by_status.sql` | 狀態分頁的場數與總收藏：我的活動依審核狀態分組（GROUP BY） | `organizer_id` |
| `merchant/venue_events_overlap.sql` | 上架表單：同場館、日期重疊的已上架活動（避免撞期） | `venue_id`, `event_id`, `start_date`, `end_date` |
| `insert_discount.sql` | 新增優惠（INSERT；早鳥沒填截止日會被驗證規則擋下） | `event_id`, `discount_type_id`, `description`, `price`, `start_date`, `end_date` |
| `list_venues.sql` | 場館下拉選單 | |
| `insert_venue.sql` | 新增場館（商家、管理員） | `name`, `city_id`, `address` |

### 管理員後台（`admin/`）

| 檔案 | 用途 |
|---|---|
| `list_events.sql` | 所有活動＋上架商家（審核狀態、關鍵字等條件由後端接在後面） |
| `update_event_status.sql` | 審核與下架：通過、退回（同時記下退回理由 `reason`）、違規下架、重新上架（UPDATE；哪些狀態能改成哪些由後端檢查） |
| `stats_events_by_status.sql` | 各審核狀態活動數（GROUP BY） |
| `organizer_history.sql` | 審核畫面：上架者其他活動各審核狀態的場數（GROUP BY；參數 `organizer_id`、`event_id`） |
| `similar_events.sql` | 審核時、商家送出前找可能重複的活動：日期重疊、已上架或待審核的其他活動（名稱相似度由後端 `api/similar.py` 計算） |
| `deactivate_ended_events.sql` | **自動下架**：已結束的「上架中」改成「已下架」（UPDATE；伺服器啟動、打開後台時執行） |
| `count_ended_active.sql` | 預覽：已結束但還在上架中的活動 |
| `pending_events.sql` | 待審核的活動（Access 後台用） |
| `reactivate_event.sql` | 重新上架並修改結束日（UPDATE） |
| `insert_event.sql` | 管理員手動新增活動（INSERT，直接上架） |
| `update_event_price.sql`、`update_discount.sql` | 修改票價、優惠（UPDATE） |
| `delete_expired_discounts.sql` | 刪除已過期優惠（DELETE；沒有截止日的不刪） |
| `delete_event.sql` | 刪除活動（DELETE；優惠、收藏會串聯刪除） |

表中從 `count_ended_active` 開始的查詢網頁不會用到，給 Access 表單的按鈕與期末報告示範 INSERT／UPDATE／DELETE。用法見 `docs/access-form-guide.md`。
