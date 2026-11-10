-- 刪除已過期的優惠（截止日期早於今天）；沒有截止日（空值）的優惠不會被刪
DELETE FROM DiscountTable
WHERE DiscountEndDate < Date();
