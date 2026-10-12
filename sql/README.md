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

| 檔案 | 用途 | 參數 |
|---|---|---|
| `list_categories.sql` | 類別下拉選單 | |
| `list_cities.sql` | 縣市下拉選單 | |
| `list_discount_types.sql` | 優惠類型勾選框 | |
| `search_events.sql` | 搜尋的基本查詢（篩選條件由後端接在後面） | |
| `event_detail.sql` | 活動詳情 | `event_id` |
| `event_sessions.sql` | 活動的所有場次與場館 | `event_id` |
| `event_discounts.sql` | 活動的所有優惠與是否有效 | `event_id` |
| `user_by_email.sql` | 登入時找使用者 | `email` |
| `user_by_id.sql` | 目前登入的使用者 | `user_id` |
| `insert_user.sql` | 註冊 | `name`, `email`, `password_hash`, `default_city_id` |
| `list_saves.sql` | 我的收藏 | `user_id` |
| `insert_save.sql` | 收藏 | `user_id`, `event_id` |
| `delete_save.sql` | 取消收藏 | `user_id`, `event_id` |

## 還沒寫、等伯元補的查詢

統計各地區活動數、熱門收藏排行、一鍵下架已結束活動（UPDATE）、管理端的新增／修改／刪除、早鳥即將截止提醒（加分）……
寫好、在 Access 測過之後放進這個資料夾，再跟晨嬡說檔名與參數，後端接上 API。
