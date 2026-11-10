-- 統計：各縣市上架中的活動數，附所屬地區
SELECT ci.CityName, ci.CityRegion, COUNT(e.EventID) AS EventCount
FROM (EventTable AS e
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
GROUP BY ci.CityName, ci.CityRegion
ORDER BY COUNT(e.EventID) DESC, ci.CityName;
