# 資料表設計（定稿：8 張表）

> 依 `HW1_TableSchemaSketch_41411016E_修改版.xlsx`（10/16 版，含 10/15 助教回饋）與專題規劃。
> 建表程式：`db/schema.py`（DAO，含驗證規則、預設值、查閱欄位、關聯）。

## 和 10/12 的 v2 提案有什麼不同

10/12 的 v2 提案（`schema-v2.md`）為了開放資料的「一場活動多個場館、多個場次」新增了場次表，變成 9 張表。
組內討論後**維持 8 張表**，v2 提案不採用：

| v2 提案 | 定稿 | 開放資料怎麼處理 |
|---|---|---|
| 新增 `SessionTable`，刪除 `EventVenue_FK` | **不加場次表**，`EventTable` 保留 `EventVenue_FK` | 一場活動在多個場館舉辦時，每個場館各建一筆活動（ETL 依場館拆分，起訖日取該場館的場次日期；優惠複製到每一筆） |
| 新增 `EventPriceNote`（票價原始說明） | **不加**；`EventOriginalPrice` 只記全票 | 學生票、敬老票等記在 `DiscountTable`；原始票價文字放在活動說明開頭（`【票價】…`） |
| `EventIsActive`（是／否） | 改成 `EventStatus`（待審核、上架中、已退回、已下架） | 開放資料匯入的活動直接是「上架中」 |
| `EventURL` 超連結型態 | 短文字 255 | 超連結欄位透過 ODBC 讀出會變成「顯示文字#網址#」 |

v2 提案中其他確認過的規則都保留：`EventOriginalPrice` 可空值（0 = 免費、空值 = 未公布）、
`DiscountEndDate` 空值 = 沒有截止日、收藏的複合唯一索引、宜蘭縣歸東部。

## 8 張表

| 資料表 | 用途 | 重點欄位 |
|---|---|---|
| `CategoryTable` | 活動類型 | `CategoryGroup`：學習類（展覽、講座、工作坊、科普展覽、研習營隊）／休閒類 |
| `CityTable` | 22 個縣市 | `CityRegion`：北部、中部、南部、東部、離島 |
| `VenueTable` | 場館 | 地址只記在這裡；`VenueCity_FK` |
| `EventTable` | 活動（系統核心） | `EventVenue_FK`、`EventOrganizer_FK`（上架商家）、`EventStatus`（審核狀態） |
| `DiscountTypeTable` | 優惠類型 | 學生優惠、早鳥優惠、敬老優惠、團體優惠 |
| `DiscountTable` | 活動優惠 | `DiscountPrice`、`DiscountStartDate`、`DiscountEndDate` |
| `UserTable` | 帳號 | `UserRole`：使用者、商家、管理員；`UserPasswordHash` |
| `SaveTable` | 收藏紀錄 | `SaveUser_FK`＋`SaveEvent_FK` 複合唯一索引 |

關係：縣市 1─N 場館 1─N 活動；類型 1─N 活動；活動 1─N 優惠 N─1 優惠類型；
使用者 N─M 活動（透過收藏紀錄）；商家（使用者）1─N 活動（上架）。

## 三種角色與審核狀態

| 角色 | 能做的事 | 怎麼建立 |
|---|---|---|
| 使用者 | 查詢、收藏 | 網頁註冊 |
| 商家 | 上架活動與優惠、修改自己的活動、新增場館 | 網頁註冊（選「商家」） |
| 管理員 | 審核（通過／退回）、違規下架、重新上架、統計 | 不開放註冊，由程式建立（測試帳號見 `db/build_test_db.py`） |

Access 沒有使用者權限分級，角色權限由後端（`api/main.py` 的 `require_role`）檢查。

```
商家新增／修改 ──▶ 待審核 ──通過──▶ 上架中 ──違規下架──▶ 已下架 ──重新上架──▶ 上架中
                     │                  │
                     └──退回──▶ 已退回   └──過了結束日期（自動下架）──▶ 已下架
                     （商家修改後回到待審核）
```

- **查詢只顯示「上架中」而且 `EventEndDate >= Date()` 的活動**，所以活動一結束就查不到。
- **自動下架**：Access 沒有排程，後端在伺服器啟動、打開商家或管理員後台時執行一個 UPDATE
  （上架中 → 已下架）。**待實作**，SQL 檔名與寫法見 `sql/README.md`。
- 開放資料、人工建檔的活動沒有商家，`EventOrganizer_FK` 一律填管理員帳號（`admin@example.com`），
  `EventDataSource` 記錄出處。

## 驗證規則（資料表層級）

| 資料表 | 規則 |
|---|---|
| CategoryTable | `CategoryGroup In ("學習類","休閒類")` |
| CityTable | `CityRegion In ("北部","中部","南部","東部","離島")` |
| EventTable | `EventEndDate >= EventStartDate`；`EventOriginalPrice >= 0`；`EventStatus In ("待審核","上架中","已退回","已下架")`，預設「待審核」 |
| DiscountTable | `DiscountPrice >= 0`；截止日不能早於開始日；**早鳥優惠（編號 2）一定要填截止日** |
| UserTable | `UserEmail Like "*@*.*"`、不可重複；`UserRole In ("使用者","商家","管理員")`，預設「使用者」 |
| SaveTable | `SaveDate` 預設 `Now()`；同一人不能重複收藏同一活動 |

## 關聯與串聯刪除

- 刪除活動：它的優惠、收藏一起刪（串聯刪除）。只想隱藏請改成「已下架」。
- 刪除使用者：他的收藏一起刪。
- 縣市、類別、場館、優惠類型、上架商家還有資料在用時，不允許刪除。
