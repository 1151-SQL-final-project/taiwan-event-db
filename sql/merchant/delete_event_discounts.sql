-- 修改活動時，先刪掉這場活動原本的優惠，再用 insert_discount.sql 重新新增
DELETE FROM DiscountTable
WHERE DiscountEvent_FK = [@event_id];
