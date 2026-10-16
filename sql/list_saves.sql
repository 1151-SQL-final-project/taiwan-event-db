-- 我的收藏：列出使用者收藏的活動，最新收藏的在前面（已下架的也列出來，網頁會標示）
SELECT e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate,
       e.EventOriginalPrice, e.EventStatus, v.VenueName, ci.CityName, sv.SaveDate
FROM (((SaveTable AS sv
INNER JOIN EventTable AS e ON sv.SaveEvent_FK = e.EventID)
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE sv.SaveUser_FK = [@user_id]
ORDER BY sv.SaveDate DESC;
