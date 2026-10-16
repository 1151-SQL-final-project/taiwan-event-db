# 資料建檔範本

整理好的資料照這幾個 CSV 的欄位填，之後用匯入程式轉進 Access。

- 用 Excel 開啟、編輯，存檔時選「**CSV UTF-8（逗號分隔）**」，中文才不會變亂碼。
- **外鍵欄位直接填名稱**，不必填編號：縣市填 `臺北市`、類別填 `展覽`、場館填場館名稱、活動填活動名稱。匯入程式會自動換成對應的編號，所以名稱要和清單上的一字不差（例如用「臺」不用「台」）。
- 日期格式 `yyyy/mm/dd`。
- 開放資料和人工建檔的活動沒有商家，匯入時上架者（`EventOrganizer_FK`）一律填管理員帳號，審核狀態直接是「上架中」。
  商家自己的活動由商家在網頁的商家後台上架，不用填這裡。

| 檔案 | 對應資料表 | 誰負責 | 備註 |
|---|---|---|---|
| `venues.csv` | VenueTable | 俊緯 | `CityName` 必須是 22 個標準縣市名稱之一 |
| `events.csv` | EventTable | 俊緯 | `VenueName` 必須是 `venues.csv` 裡的場館；票價規則見下方 |
| `discounts.csv` | DiscountTable | 揚健 | `SourceURL`、`RecordedBy`、`RecordedDate` 只用於引用清單，不會匯入資料表 |

## 一場活動在多個場館舉辦

資料表是 8 張表的設計，**一筆活動只有一個場館**（`EventVenue_FK`）。巡演、多地舉辦的活動，
在 `events.csv` 每個場館寫一列（活動名稱相同），起訖日期填該場館的日期；`discounts.csv` 每一筆活動都要寫優惠。

## 票價規則（EventOriginalPrice）

`EventOriginalPrice` 只填**全票**價格；學生票、敬老票等其他票價寫在 `discounts.csv`（優惠類型選學生優惠、敬老優惠…）。

| 原始寫法 | EventOriginalPrice | 其他票價 |
|---|---|---|
| 300 | `300` | |
| 全票 500、學生票 300 | `500` | `discounts.csv` 加一筆學生優惠 300 |
| 500–2000（依座位） | `500`（最便宜的全票） | 原始寫法可以寫在 `EventDescription` |
| 免費 | `0` | |
| 依現場公告、未公布 | **留空**（不要填 0，0 代表免費） | |

## 優惠日期

- `DiscountStartDate` 留空：優惠期間和活動期間相同。
- `DiscountEndDate` 留空：沒有截止日，一直有效。**早鳥優惠一定要填截止日**（資料表驗證規則會擋）。
