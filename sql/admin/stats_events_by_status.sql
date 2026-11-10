-- 統計：各審核狀態的活動數
SELECT EventStatus, COUNT(EventID) AS EventCount
FROM EventTable
GROUP BY EventStatus
ORDER BY COUNT(EventID) DESC;
