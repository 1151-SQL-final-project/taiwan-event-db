-- 活動詳情：所有場次與場館（一場活動可能在多個場館、多個時間舉行）
SELECT s.SessionID, s.SessionStartTime, s.SessionEndTime,
       v.VenueID, v.VenueName, v.VenueAddress, ci.CityName, ci.CityRegion
FROM (SessionTable AS s
INNER JOIN VenueTable AS v ON s.SessionVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE s.SessionEvent_FK = [@event_id]
ORDER BY s.SessionStartTime;
