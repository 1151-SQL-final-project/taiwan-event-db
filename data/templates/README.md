# 資料建檔範本

整理好的資料照這幾個 CSV 的欄位填，之後用匯入程式轉進 Access。

- 用 Excel 開啟、編輯，存檔時選「**CSV UTF-8（逗號分隔）**」，中文才不會變亂碼。
- **外鍵欄位直接填名稱**，不必填編號：縣市填 `臺北市`、類別填 `展覽`、場館填場館名稱、活動填活動名稱。匯入程式會自動換成對應的編號，所以名稱要和清單上的一字不差（例如用「臺」不用「台」）。
- 日期格式 `yyyy/mm/dd`，時間格式 `yyyy/mm/dd hh:mm`。

| 檔案 | 對應資料表 | 誰負責 | 備註 |
|---|---|---|---|
| `venues.csv` | VenueTable | 俊緯 | `CityName` 必須是 22 個標準縣市名稱之一 |
| `events.csv` | EventTable | 俊緯 | 票價規則見下方 |
| `sessions.csv` | SessionTable | 俊緯 | 一場活動有幾個場次／場館就寫幾列；展覽類寫一列，起訖等於展期 |
| `discounts.csv` | DiscountTable | 揚健 | `SourceURL`、`RecordedBy`、`RecordedDate` 只用於引用清單，不會匯入資料表 |

## 票價規則（EventOriginalPrice）

| 原始寫法 | EventOriginalPrice | EventPriceNote |
|---|---|---|
| 300 | `300` | 留空 |
| 500–2000（依座位） | `500`（取最低價） | `500–2000（依座位）` |
| 免費 | `0` | 可留空，或寫「免費，需報名」 |
| 依現場公告、未公布 | **留空**（不要填 0，0 代表免費） | `依現場公告` |

## 優惠日期

- `DiscountStartDate` 留空：優惠期間和活動期間相同。
- `DiscountEndDate` 留空：沒有截止日，一直有效。**早鳥優惠一定要填截止日。**
