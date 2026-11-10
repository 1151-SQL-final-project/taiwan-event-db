-- 登入：用信箱找使用者（密碼比對在後端做，SQL 不碰原始密碼）
SELECT UserID, UserName, UserEmail, UserPasswordHash, UserRole
FROM UserTable
WHERE UserEmail = [@email];
