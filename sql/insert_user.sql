-- 註冊：新增使用者（密碼已由後端雜湊）
INSERT INTO UserTable (UserName, UserEmail, UserPasswordHash, UserDefaultCity_FK)
VALUES ([@name], [@email], [@password_hash], [@default_city_id]);
