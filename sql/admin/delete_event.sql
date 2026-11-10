-- 刪除活動。關聯設了串聯刪除，這場活動的優惠、收藏會一起刪掉；只想隱藏請改用下架
DELETE FROM EventTable
WHERE EventID = [@event_id];
