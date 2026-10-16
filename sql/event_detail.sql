-- 活動詳情：活動、類別、場館與縣市、上架商家。審核狀態也一起查，後端決定誰看得到
SELECT e.EventID, e.EventTitle, e.EventCategory_FK, c.CategoryName, c.CategoryGroup,
       e.EventStartDate, e.EventEndDate, e.EventOriginalPrice, e.EventURL, e.EventDataSource,
       e.EventStatus, e.EventDescription, e.EventOrganizer_FK, u.UserName AS OrganizerName,
       e.EventVenue_FK, v.VenueName, v.VenueAddress, ci.CityName, ci.CityRegion
FROM (((EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID)
INNER JOIN UserTable AS u ON e.EventOrganizer_FK = u.UserID
WHERE e.EventID = [@event_id];
