# db

放 Access 主檔（活動資料庫.accdb）。

- 只有晏均修改並上傳這裡的檔案。
- 其他人要改表或加欄位，請在群組提出，由她更新。
- 要測試時，先複製一份到儲存庫外面再改。

## 測試用資料庫

`build_test_db.py` 會產生 `test_events.accdb`：照 [docs/schema.md](../docs/schema.md) 的 8 張表建表（結構在 `schema.py`），塞少量假資料（三種角色的帳號、四種審核狀態的活動），給後端和網頁在主檔完成前測試用。

```powershell
.venv\Scripts\python db\build_test_db.py
```

- 每次執行都會**整個重建**，測試時改壞了資料，重跑一次就好。
- `test_events.accdb` 不會上傳（已列在 `.gitignore`），每個人自己產生。
- 它**不是主檔**，正式資料請放進晏均維護的主檔。
