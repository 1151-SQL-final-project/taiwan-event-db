-- 商家後台的狀態分頁與總收藏：我的活動依審核狀態分組，各有幾場、共被收藏幾次
-- 先把收藏依活動分組計數（子查詢 s），再接到活動表；沒人收藏的活動算 0
SELECT e.EventStatus, COUNT(*) AS EventCount,
       SUM(IIf(s.SaveCount IS NULL, 0, s.SaveCount)) AS SaveCount
FROM EventTable AS e
LEFT JOIN (SELECT SaveEvent_FK, COUNT(*) AS SaveCount FROM SaveTable GROUP BY SaveEvent_FK) AS s
  ON e.EventID = s.SaveEvent_FK
WHERE e.EventOrganizer_FK = [@organizer_id]
GROUP BY e.EventStatus;
