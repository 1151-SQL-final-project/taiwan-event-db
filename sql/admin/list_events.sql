-- 管理員後台：所有活動（含上架商家），審核狀態等條件由後端接在後面；排序也由後端加上
SELECT e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate, e.EventOriginalPrice,
       e.EventStatus, e.EventRejectReason, e.EventSaleStartDate, e.EventDataSource,
       v.VenueName, ci.CityName, ci.CityRegion,
       e.EventOrganizer_FK, u.UserName AS OrganizerName, u.UserRole AS OrganizerRole
FROM (((EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID)
INNER JOIN UserTable AS u ON e.EventOrganizer_FK = u.UserID
