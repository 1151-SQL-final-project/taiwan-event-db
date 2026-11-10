-- 場館清單（商家上架活動時選場館）
SELECT v.VenueID, v.VenueName, v.VenueAddress, v.VenueCity_FK, ci.CityName
FROM VenueTable AS v
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
ORDER BY ci.CityID, v.VenueName;
