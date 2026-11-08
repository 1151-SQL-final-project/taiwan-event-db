# Google Sheet Query 版本（加分項目）

> W13 教的 Google Visualization API Query Language。把 Access 裡的查詢，改用 Google 試算表的 `QUERY()` 函數做一次，比較兩者的差異。
>
> ⚠ 下列公式依照官方語法撰寫，**尚未在 Google 試算表實際測試**。
> 用 `docs/google_sheet_check.gs` 可以一次自動檢查（免費，不需要 Google Cloud）：
> 匯入資料後，「擴充功能」→「Apps Script」貼上該檔內容 → 執行 `checkAllQueries`。
> 它會把 8 個公式各放一個工作表，並用程式**另外算一次答案**（各地區筆數、免費活動數、收藏排行…）比對，
> 結果寫在「檢查結果」工作表。

## 1. 準備資料

1. 在專案根目錄執行（需先跑過 `db\build_db.py`）：
   ```powershell
   .venv\Scripts\python etl\export_sheets.py
   ```
   產生 `data/sheets/events_flat.csv`。
2. 開一個新的 Google 試算表 →「檔案」→「匯入」→「上傳」選這個 CSV →「插入新工作表」。
3. 把工作表改名為 **`活動`**（下方公式都用這個名稱）。

欄位對照（QUERY 用欄位字母）：

| 欄 | 內容 | 欄 | 內容 |
|---|---|---|---|
| A | 活動編號 | H | 學生優惠（是／否） |
| B | 活動名稱 | I | 早鳥優惠（是／否） |
| C | 類別 | J | 縣市 |
| D | 開始日期 | K | 地區 |
| E | 結束日期 | L | 場館 |
| F | 原價（全票；空白＝未公布） | M | 類別分組（學習類／休閒類） |
| G | 目前最低優惠價 | N | 收藏數 |

> **為什麼要攤平成一張表？** Google QUERY 只能查一個範圍，**沒有 JOIN**。Access 裡分成 8 張表（正規化），匯出時先 JOIN 好（反正規化）。這正好可以在報告裡說明正規化的取捨。

## 2. 查詢範例

在另一個工作表的 A1 貼上公式即可。

### ① 各地區活動數（對照 `統計_各地區活動數`）

```
=QUERY(活動!A:N, "select K, count(A) where A is not null group by K order by count(A) desc label K '地區', count(A) '活動數'", 1)
```

### ② 各類別活動數與平均票價（對照 `統計_各類別活動數`）

```
=QUERY(活動!A:N, "select C, count(A), avg(F) where A is not null group by C order by count(A) desc label C '類別', count(A) '活動數', avg(F) '平均原價'", 1)
```

`avg()` 會自動略過空白（票價不明），和 Access 的 `Avg()` 略過 Null 一樣。

### ③ 北部、有學生優惠、優惠價 300 元以下

```
=QUERY(活動!A:N, "select B, J, F, G where K = '北部' and H = '是' and G <= 300 order by G label B '活動', J '縣市', F '原價', G '學生價'", 1)
```

### ④ 今天到月底之間有在舉辦的活動（日期區間重疊）

```
=QUERY(活動!A:N, "select B, C, D, E, J where D <= date '" & TEXT(EOMONTH(TODAY(), 0), "yyyy-mm-dd") & "' and E >= date '" & TEXT(TODAY(), "yyyy-mm-dd") & "' order by E", 1)
```

QUERY 的日期常數要寫成 `date 'yyyy-mm-dd'`，所以用 `TEXT()` 把 `TODAY()` 轉成字串再接起來。
Access 的寫法是 `EventStartDate <= #2026/10/31# AND EventEndDate >= Date()`。

### ⑤ 免費活動

```
=QUERY(活動!A:N, "select B, C, J, D, E where F = 0 order by D", 1)
```

### ⑥ 熱門收藏前 10 名（對照 `統計_熱門收藏排行`）

```
=QUERY(活動!A:N, "select B, C, N where N > 0 order by N desc limit 10 label B '活動', C '類別', N '收藏數'", 1)
```

Access 用 `SELECT TOP 10 … ORDER BY COUNT(…) DESC`；QUERY 用 `limit 10`。

### ⑦ 樞紐：各類別 × 各地區活動數

```
=QUERY(活動!A:N, "select C, count(A) where A is not null group by C pivot K", 1)
```

`pivot` 是 QUERY 特有的語法，Access 要用 `TRANSFORM … PIVOT`（交叉資料表查詢）才做得到。

### ⑧ 讓使用者自己選條件（下拉選單＋QUERY）

1. 在工作表 `查詢` 的 B1 放下拉選單：「資料」→「資料驗證」→「下拉式選單」，選項：北部、中部、南部、東部、離島。
2. B2 放類別下拉選單（展覽、講座、工作坊…）。
3. A4 貼上：

```
=QUERY(活動!A:N, "select B, C, J, D, E, F, G where K = '" & B1 & "' and C = '" & B2 & "' order by D", 1)
```

改下拉選單，結果就會跟著變——等於一個不用寫程式的簡易搜尋頁。

### ⑨ 學習類活動（對照網頁「類型：學習類」）

```
=QUERY(活動!A:N, "select B, C, J, D, E, G where M = '學習類' order by D", 1)
```

Access 的寫法是 `WHERE c.CategoryGroup = '學習類'`，要先 JOIN `CategoryTable`；試算表已經攤平，直接比對 M 欄。
（`google_sheet_check.gs` 只自動檢查 ①～⑧。）

## 3. Access SQL 與 Google QUERY 對照（報告可用）

| 功能 | Access SQL | Google QUERY |
|---|---|---|
| 選欄位 | `SELECT EventTitle` | `select B`（欄位字母） |
| 多表關聯 | `INNER JOIN … ON …` | 不支援，要先攤平 |
| 前 N 筆 | `SELECT TOP 10` | `limit 10` |
| 日期常數 | `#2026/10/12#`、`Date()` | `date '2026-10-12'`，今天要用 `TODAY()` 組字串 |
| 模糊搜尋 | `LIKE '*恐龍*'`（ODBC 用 `%`） | `contains '恐龍'` 或 `like '%恐龍%'` |
| 欄位別名 | `AS 活動數` | `label count(A) '活動數'` |
| 樞紐 | `TRANSFORM … PIVOT` | `pivot` |
| 不重複計數 | 不支援 `COUNT(DISTINCT)`，用子查詢 | 不支援，用兩層 QUERY |
| 參數 | `[請輸入 幾天內]` 執行時跳出輸入框 | 用儲存格＋字串串接 |
