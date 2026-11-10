-- 管理員審核：上架者其他活動的審核紀錄（各審核狀態幾場，不含正在審核的這場），
-- 讓管理員知道是第一次上架的商家，還是常被退回的商家
SELECT e.EventStatus, COUNT(*) AS EventCount
FROM EventTable AS e
WHERE e.EventOrganizer_FK = [@organizer_id] AND e.EventID <> [@event_id]
GROUP BY e.EventStatus;
