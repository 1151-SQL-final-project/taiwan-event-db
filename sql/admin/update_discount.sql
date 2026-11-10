-- 修改優惠價格與截止日期（例如早鳥延長）
UPDATE DiscountTable
SET DiscountPrice = [@price], DiscountEndDate = [@end_date]
WHERE DiscountID = [@discount_id];
