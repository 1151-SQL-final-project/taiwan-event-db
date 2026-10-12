-- 活動詳情（基本資料）
SELECT e.EventID, e.EventTitle, c.CategoryName,
       e.EventStartDate, e.EventEndDate, e.EventOriginalPrice, e.EventPriceNote,
       e.EventURL, e.EventDataSource, e.EventIsActive, e.EventDescription
FROM EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID
WHERE e.EventID = [@event_id];
