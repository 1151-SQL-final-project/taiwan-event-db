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

## 後端目前用到的查詢

改這些檔案時，**欄位名稱（SELECT 出來的欄位）和參數名稱不要變**，網頁靠這些名稱顯示資料。
資料表是 8 張表的定稿（見 [docs/schema.md](../docs/schema.md)）。「公開活動」的條件是
`EventStatus = '上架中' AND EventEndDate >= Date()`（已寫在 `search_events.sql`）。

| 檔案 | 用途 | 參數 |
|---|---|---|
| `list_categories.sql` | 類別下拉選單（含 CategoryGroup：學習類／休閒類） | |
| `list_cities.sql` | 縣市下拉選單 | |
| `list_discount_types.sql` | 優惠類型勾選框 | |
| `search_events.sql` | 搜尋的基本查詢（活動＋類別＋場館＋縣市；篩選條件由後端接在後面） | |
| `event_detail.sql` | 活動詳情（含場館地址、上架商家、審核狀態） | `event_id` |
| `event_discounts.sql` | 活動的所有優惠與是否有效 | `event_id` |
| `user_by_email.sql` | 登入時找使用者 | `email` |
| `user_by_id.sql` | 目前登入的使用者（含角色 UserRole） | `user_id` |
| `insert_user.sql` | 註冊 | `name`, `email`, `password_hash`, `role`, `default_city_id` |
| `list_saves.sql` | 我的收藏 | `user_id` |
| `insert_save.sql` | 收藏 | `user_id`, `event_id` |
| `delete_save.sql` | 取消收藏 | `user_id`, `event_id` |

## 還沒寫的查詢（伯元）

寫好、在 Access 測過之後放進這個資料夾，**檔名和參數名稱照下表**，後端（`api/main.py` 裡回傳 501 的 API）就能直接接上。
商家用的放 `sql/merchant/`，管理員用的放 `sql/admin/`。

### 商家後台

| 檔案 | 用途 | 參數 |
|---|---|---|
| `list_venues.sql` | 場館清單（VenueID、VenueName、VenueAddress、VenueCity_FK、CityName） | |
| `insert_venue.sql` | 新增場館（INSERT） | `name`, `city_id`, `address` |
| `merchant/list_my_events.sql` | 我上架的所有活動，各種審核狀態都列出來 | `organizer_id` |
| `merchant/insert_event.sql` | 上架活動（INSERT）：`EventStatus` 填 `'待審核'`、`EventDataSource` 填 `'商家上架'` | `category_id`, `venue_id`, `title`, `start_date`, `end_date`, `price`, `url`, `organizer_id`, `description` |
| `merchant/update_event.sql` | 修改自己的活動（UPDATE）：改回 `'待審核'`；`WHERE EventID = [@event_id] AND EventOrganizer_FK = [@organizer_id]` | 同上＋`event_id` |
| `merchant/delete_event_discounts.sql` | 修改活動時先刪掉原本的優惠（DELETE） | `event_id` |
| `insert_discount.sql` | 新增優惠（INSERT） | `event_id`, `discount_type_id`, `description`, `price`, `start_date`, `end_date` |

### 管理員後台

| 檔案 | 用途 | 參數 |
|---|---|---|
| `admin/deactivate_ended_events.sql` | **自動下架**：`UPDATE EventTable SET EventStatus = '已下架' WHERE EventStatus = '上架中' AND EventEndDate < Date()` | |
| `admin/list_events.sql` | 所有活動＋上架商家名稱（JOIN UserTable），不寫 WHERE，條件由後端接 | |
| `admin/update_event_status.sql` | 審核與下架（UPDATE `EventStatus`） | `status`, `event_id` |
| `admin/stats_events_by_status.sql` | 各審核狀態活動數（GROUP BY） | |
| `stats_events_by_region.sql` | 各地區上架中的活動數（活動 → 場館 → 縣市 JOIN＋GROUP BY） | |
| `popular_saves.sql` | 熱門收藏排行前 10 名（JOIN＋GROUP BY＋TOP） | |

加分：`early_bird_ending_soon.sql`（N 天內截止的早鳥優惠，參數 `days`）。
