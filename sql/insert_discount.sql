-- 新增優惠（開始日期留空 = 與活動期間相同；截止日期留空 = 沒有截止日；早鳥優惠一定要填截止日）
INSERT INTO DiscountTable (DiscountEvent_FK, DiscountType_FK, DiscountDescription,
                           DiscountPrice, DiscountStartDate, DiscountEndDate)
VALUES ([@event_id], [@discount_type_id], [@description], [@price], [@start_date], [@end_date]);
