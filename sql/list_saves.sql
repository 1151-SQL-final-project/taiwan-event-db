-- 我的收藏：列出使用者收藏的活動，最新收藏的在前面
SELECT e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate,
       e.EventOriginalPrice, e.EventPriceNote, e.EventIsActive, sv.SaveDate
FROM (SaveTable AS sv
INNER JOIN EventTable AS e ON sv.SaveEvent_FK = e.EventID)
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID
WHERE sv.SaveUser_FK = [@user_id]
ORDER BY sv.SaveDate DESC;
