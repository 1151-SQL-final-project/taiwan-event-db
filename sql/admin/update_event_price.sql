-- 修改活動票價（全票）；學生票、敬老票等其他票價改 DiscountTable
UPDATE EventTable
SET EventOriginalPrice = [@price]
WHERE EventID = [@event_id];
