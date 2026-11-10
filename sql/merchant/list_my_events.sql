-- 商家後台：我上架的所有活動（各種審核狀態都列出來），最新的在前面
-- 圖片、網址與目前最低優惠價（BestDiscountPrice，規則同 search_events.sql）讓展開後的樣子和活動卡片一樣
-- EarlyBirdEnd：還沒截止的早鳥優惠中最早的截止日（沒有就是空值），清單上標「早鳥 11/7 截止」
SELECT e.EventID, e.EventTitle, c.CategoryName, e.EventStartDate, e.EventEndDate, e.EventOriginalPrice,
       e.EventStatus, e.EventRejectReason, e.EventSaleStartDate, e.EventImageURL, e.EventURL, v.VenueName, ci.CityName,
       (SELECT MIN(d.DiscountPrice) FROM DiscountTable AS d WHERE d.DiscountEvent_FK = e.EventID
          AND (d.DiscountStartDate IS NULL OR d.DiscountStartDate <= Date())
          AND (d.DiscountEndDate IS NULL OR d.DiscountEndDate >= Date())) AS BestDiscountPrice,
       (SELECT COUNT(*) FROM DiscountTable AS dc WHERE dc.DiscountEvent_FK = e.EventID) AS DiscountCount,
       (SELECT COUNT(*) FROM SaveTable AS sv WHERE sv.SaveEvent_FK = e.EventID) AS SaveCount,
       (SELECT MIN(eb.DiscountEndDate) FROM DiscountTable AS eb INNER JOIN DiscountTypeTable AS t ON eb.DiscountType_FK = t.DiscountTypeID
        WHERE eb.DiscountEvent_FK = e.EventID AND t.DiscountTypeName = '早鳥優惠' AND eb.DiscountEndDate >= Date()) AS EarlyBirdEnd
FROM ((EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE e.EventOrganizer_FK = [@organizer_id]
ORDER BY e.EventID DESC;
