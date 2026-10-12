-- 收藏活動。SaveDate 由資料表預設值 Now() 自動填入；
-- 重複收藏會被 SaveUser_FK + SaveEvent_FK 的複合唯一索引擋下
INSERT INTO SaveTable (SaveUser_FK, SaveEvent_FK)
VALUES ([@user_id], [@event_id]);
