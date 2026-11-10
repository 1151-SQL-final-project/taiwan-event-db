-- 熱門收藏排行：上架中的活動依被收藏次數排序，取前 10 名（同票數時 Access 的 TOP 會一起列出）
SELECT TOP 10 e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate,
       COUNT(sv.SaveID) AS SaveCount
FROM (SaveTable AS sv
INNER JOIN EventTable AS e ON sv.SaveEvent_FK = e.EventID)
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID
WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
GROUP BY e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate
ORDER BY COUNT(sv.SaveID) DESC, e.EventID;
