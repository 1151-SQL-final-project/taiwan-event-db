-- 搜尋活動的「基本查詢」：只列「上架中」而且還沒結束的活動，並算出目前有效優惠中的最低價。
-- 還沒結束（EventEndDate >= Date()）也寫在這裡：就算自動下架還沒執行，已結束的活動也查不到。
-- 地區、縣市、日期、類別、優惠類型等篩選條件，由後端（api/main.py 的 search_events）
-- 依使用者勾選的項目接在 WHERE 後面，排序也由後端加上，所以這裡不寫 ORDER BY。
-- 「目前有效的優惠」：開始日期空值或已開始，且截止日期空值（沒有截止日）或還沒過。
SELECT e.EventID, e.EventTitle, c.CategoryName, c.CategoryGroup,
       e.EventStartDate, e.EventEndDate, e.EventOriginalPrice,
       v.VenueName, ci.CityName, ci.CityRegion,
       (SELECT MIN(d.DiscountPrice)
          FROM DiscountTable AS d
         WHERE d.DiscountEvent_FK = e.EventID
           AND (d.DiscountStartDate IS NULL OR d.DiscountStartDate <= Date())
           AND (d.DiscountEndDate IS NULL OR d.DiscountEndDate >= Date())) AS BestDiscountPrice
FROM ((EventTable AS e
INNER JOIN CategoryTable AS c ON e.EventCategory_FK = c.CategoryID)
INNER JOIN VenueTable AS v ON e.EventVenue_FK = v.VenueID)
INNER JOIN CityTable AS ci ON v.VenueCity_FK = ci.CityID
WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
