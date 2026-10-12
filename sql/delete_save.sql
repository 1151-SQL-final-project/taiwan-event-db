-- 取消收藏
DELETE FROM SaveTable
WHERE SaveUser_FK = [@user_id] AND SaveEvent_FK = [@event_id];
