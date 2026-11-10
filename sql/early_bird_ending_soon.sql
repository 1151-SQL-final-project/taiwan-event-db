-- 早鳥即將截止：截止日在今天到 N 天後之間的早鳥優惠（只看上架中的活動），最快截止的排前面
SELECT e.EventID, e.EventTitle, e.EventOriginalPrice, d.DiscountPrice, d.DiscountDescription,
       d.DiscountEndDate, DateDiff('d', Date(), d.DiscountEndDate) AS DaysLeft
FROM (DiscountTable AS d
INNER JOIN DiscountTypeTable AS t ON d.DiscountType_FK = t.DiscountTypeID)
INNER JOIN EventTable AS e ON d.DiscountEvent_FK = e.EventID
WHERE t.DiscountTypeName = '早鳥優惠'
  AND e.EventStatus = '上架中'
  AND d.DiscountEndDate BETWEEN Date() AND DateAdd('d', [@days], Date())
ORDER BY d.DiscountEndDate, e.EventID;
