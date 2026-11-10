-- 找「可能重複」的活動：和指定活動日期重疊、還沒結束，而且已上架或也在待審核的其他活動。
-- 管理員審核時、商家送出審核前都會用（商家上架新活動時 event_id 填 0）。
-- 名稱是否相似 Access SQL 做不到（沒有模糊比對），由後端（api/similar.py 的 find_similar）
-- 對這裡撈出的候選活動計算名稱相似度，再加上場館、縣市、網址是否相同，決定要不要提醒。
SELECT e.EventID, e.EventTitle, e.EventStartDate, e.EventEndDate, e.EventStatus, e.EventURL, e.EventOrganizer_FK,
       e.EventVenue_FK, v.VenueName, ci.CityName, u.UserName AS OrganizerName
FROM ((EventTable AS e
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID)
INNER JOIN UserTable AS u ON e.EventOrganizer_FK = u.UserID
WHERE e.EventID <> [@event_id]
  AND e.EventStatus IN ('上架中', '待審核')
  AND e.EventEndDate >= Date()
  AND e.EventStartDate <= [@end_date] AND e.EventEndDate >= [@start_date]
ORDER BY e.EventID;
