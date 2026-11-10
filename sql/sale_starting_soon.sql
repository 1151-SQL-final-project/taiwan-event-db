-- 即將開賣：上架中、還沒結束，而且開賣時間在現在到 N 天後之間的活動，最快開賣的排前面
-- 熱門演唱會常常一開賣就賣完，所以要用到「時、分」：比較 Now() 而不是 Date()
SELECT e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate, e.EventOriginalPrice,
       e.EventSaleStartDate, v.VenueName, ci.CityName,
       DateDiff('d', Date(), e.EventSaleStartDate) AS DaysLeft
FROM ((EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
  AND e.EventSaleStartDate BETWEEN Now() AND DateAdd('d', [@days], Now())
ORDER BY e.EventSaleStartDate, e.EventID;
