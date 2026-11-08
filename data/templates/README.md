# 資料建檔範本

整理好的資料照這幾個 CSV 的欄位填，之後用匯入程式轉進 Access。

- 用 Excel 開啟、編輯，存檔時選「**CSV UTF-8（逗號分隔）**」，中文才不會變亂碼。
- **外鍵欄位直接填名稱**，不必填編號：縣市填 `臺北市`、類別填 `展覽`、場館填場館名稱。匯入程式會自動換成對應的編號，所以名稱要和清單上的一字不差（例如用「臺」不用「台」）。
- **`EventKey` 是活動的代號**，用來把優惠對到活動。人工建檔的活動自己編 `M001`、`M002`…；
  幫開放資料的活動補優惠時，從 `data/review/moc_discount_candidates.csv` 複製那一列的 `EventKey`。
  `EventKey` 留空時改用活動名稱對應（同名活動會對錯，盡量填）。
- 日期格式 `yyyy/mm/dd`。`events.csv` 的 `EventSaleStartDate`（開賣時間）要寫到時、分，例如 `2026/11/01 12:00`；不用買票或還不知道就留空。選填的 `EventImageURL`（活動圖片的 https 網址）、`EventShowTimes`（場次時間，格式 `2026-11-27T19:30|2026-11-27T21:00`，多場用 `;` 分開）沒有就留空。
- **填好的檔案放在 `data/manual/`**（同名檔案：`venues.csv`、`events.csv`、`discounts.csv`），
  執行 `db\build_db.py` 會和開放資料一起匯入。有錯的資料列會列在 `data/review/load_errors.csv`。
- 人工建檔和開放資料的活動，上架者（`EventOrganizer_FK`）都是管理員帳號，審核狀態直接是「上架中」。
  商家自己的活動請商家在網頁的「商家後台」上架，不用填這裡。

| 檔案 | 對應資料表 | 誰負責 | 備註 |
|---|---|---|---|
| `venues.csv` | VenueTable | 俊緯 | `CityName` 必須是 22 個標準縣市名稱之一 |
| `events.csv` | EventTable | 俊緯 | `VenueName` 必須是 `venues.csv` 或開放資料裡的場館；票價規則見下方 |
| `discounts.csv` | DiscountTable | 揚健 | `SourceURL`、`RecordedBy`、`RecordedDate` 只用於引用清單，不會匯入資料表。可以從 `data/clean/moc_discounts.csv`（程式自動擷取、標「待確認」）逐筆到官網核對 |

## 一場活動在多個場館舉辦

資料表是 8 張表的設計，**一筆活動只有一個場館**（`EventVenue_FK`）。巡演、多地舉辦的活動，
在 `events.csv` 每個場館寫一列，`EventKey` 填一樣的，起訖日期填該場館的日期。
`discounts.csv` 只要寫一次，匯入時會複製到同一個 `EventKey` 的每一筆活動。

## 票價規則（EventOriginalPrice）

`EventOriginalPrice` 只填**全票**價格；學生票、敬老票等其他票價寫在 `discounts.csv`（優惠類型選學生優惠、敬老優惠…）。
`EventPriceNote` 不是資料表欄位，只是保留原始寫法：匯入時會加在活動說明的開頭（`【票價】…`）。

| 原始寫法 | EventOriginalPrice | EventPriceNote |
|---|---|---|
| 300 | `300` | 留空 |
| 全票 500、學生票 300 | `500` | 留空；學生票寫一筆學生優惠 300 |
| 500–2000（依座位） | `500`（最便宜的全票） | `500–2000（依座位）` |
| 免費 | `0` | 可留空，或寫「免費，需報名」 |
| 依現場公告、未公布 | **留空**（不要填 0，0 代表免費） | `依現場公告` |

## 優惠日期

- `DiscountStartDate` 留空：優惠期間和活動期間相同。
- `DiscountEndDate` 留空：沒有截止日，一直有效。**早鳥優惠一定要填截止日**（資料表驗證規則會擋）。

## 修正失效的活動連結

`data/manual/link_fixes.csv`（`OldURL`、`NewURL`、`Reason`、`CheckedDate`）：開放資料的活動連結失效時記在這裡，`etl/clean_moc.py` 每次清理都會套用。`NewURL` 留空 = 清空連結，活動頁就不顯示「活動官網」按鈕。
