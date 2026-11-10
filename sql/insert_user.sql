-- 註冊：新增使用者（密碼已由後端雜湊）。角色只能是「使用者」或「商家」，由後端檢查；管理員不開放註冊
INSERT INTO UserTable (UserName, UserEmail, UserPasswordHash, UserRole)
VALUES ([@name], [@email], [@password_hash], [@role]);
