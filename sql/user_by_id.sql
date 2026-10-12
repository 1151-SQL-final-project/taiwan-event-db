-- 取得登入中的使用者資料（不回傳密碼雜湊）
SELECT u.UserID, u.UserName, u.UserEmail, u.UserDefaultCity_FK, ci.CityName
FROM UserTable AS u
LEFT JOIN CityTable AS ci ON u.UserDefaultCity_FK = ci.CityID
WHERE u.UserID = [@user_id];
