-- 活動詳情：所有優惠，並標出目前是否有效（截止日期空值 = 沒有截止日）
SELECT d.DiscountID, t.DiscountTypeName, d.DiscountDescription, d.DiscountPrice,
       d.DiscountStartDate, d.DiscountEndDate,
       IIf((d.DiscountStartDate IS NULL OR d.DiscountStartDate <= Date())
           AND (d.DiscountEndDate IS NULL OR d.DiscountEndDate >= Date()), True, False) AS IsValidNow
FROM DiscountTable AS d
INNER JOIN DiscountTypeTable AS t ON d.DiscountType_FK = t.DiscountTypeID
WHERE d.DiscountEvent_FK = [@event_id]
ORDER BY d.DiscountPrice;
