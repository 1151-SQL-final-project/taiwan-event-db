-- 取得登入中的使用者資料（不回傳密碼雜湊）；UserRole 決定能用哪些功能
SELECT UserID, UserName, UserEmail, UserRole
FROM UserTable
WHERE UserID = [@user_id];
