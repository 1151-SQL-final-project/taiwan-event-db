-- 上架表單：同一個場館、日期重疊、已上架而且還沒結束的其他活動（讓商家選日期時避開撞期）
-- 修改活動時 event_id 填自己的編號，排除自己；上架新活動填 0
SELECT e.EventID, e.EventTitle, e.EventStartDate, e.EventEndDate, c.CategoryName
FROM EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID
WHERE e.EventVenue_FK = [@venue_id] AND e.EventID <> [@event_id]
  AND e.EventStatus = '上架中' AND e.EventEndDate >= Date()
  AND e.EventStartDate <= [@end_date] AND e.EventEndDate >= [@start_date]
ORDER BY e.EventStartDate, e.EventID;
