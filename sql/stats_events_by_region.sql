-- 統計：各地區上架中的活動數（活動 → 場館 → 縣市 → 地區）
SELECT ci.CityRegion, COUNT(e.EventID) AS EventCount
FROM (EventTable AS e
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
GROUP BY ci.CityRegion
ORDER BY COUNT(e.EventID) DESC;
