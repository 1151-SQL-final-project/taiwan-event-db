-- 修改名稱：使用者的暱稱、商家的商家名稱（活動頁顯示的「商家：…」就是這個名稱）
UPDATE UserTable
SET UserName = [@name]
WHERE UserID = [@user_id];
