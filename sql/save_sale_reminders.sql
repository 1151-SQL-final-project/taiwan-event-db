-- 開賣提醒：我收藏的活動中，N 天內就要開賣的（還沒開賣才提醒），最快開賣的排前面
SELECT e.EventID, e.EventTitle, e.EventSaleStartDate,
       DateDiff('d', Date(), e.EventSaleStartDate) AS DaysLeft
FROM SaveTable AS sv
INNER JOIN EventTable AS e ON sv.SaveEvent_FK = e.EventID
WHERE sv.SaveUser_FK = [@user_id]
  AND e.EventStatus = '上架中'
  AND e.EventSaleStartDate BETWEEN Now() AND DateAdd('d', [@days], Now())
ORDER BY e.EventSaleStartDate;
