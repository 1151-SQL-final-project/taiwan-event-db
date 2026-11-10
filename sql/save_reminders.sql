-- 收藏提醒：我收藏的活動中，N 天內就要截止的優惠（早鳥、學生等都算）
SELECT e.EventID, e.EventTitle, t.DiscountTypeName, d.DiscountPrice, d.DiscountEndDate,
       DateDiff('d', Date(), d.DiscountEndDate) AS DaysLeft
FROM ((SaveTable AS sv
INNER JOIN EventTable AS e ON sv.SaveEvent_FK = e.EventID)
INNER JOIN DiscountTable AS d ON d.DiscountEvent_FK = e.EventID)
INNER JOIN DiscountTypeTable AS t ON d.DiscountType_FK = t.DiscountTypeID
WHERE sv.SaveUser_FK = [@user_id]
  AND e.EventStatus = '上架中'
  AND d.DiscountEndDate BETWEEN Date() AND DateAdd('d', [@days], Date())
ORDER BY d.DiscountEndDate;
