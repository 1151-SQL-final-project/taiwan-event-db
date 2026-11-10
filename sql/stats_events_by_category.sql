-- 統計：各類別上架中的活動數，以及有標價活動的平均原價（票價未公布的空值不列入平均）
SELECT c.CategoryName, c.CategoryGroup, COUNT(e.EventID) AS EventCount,
       Round(Avg(e.EventOriginalPrice), 0) AS AvgPrice,
       CLng(Sum(IIf(e.EventOriginalPrice = 0, 1, 0))) AS FreeCount
FROM CategoryTable AS c
INNER JOIN EventTable AS e ON c.CategoryID = e.EventCategory_FK
WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date()
GROUP BY c.CategoryName, c.CategoryGroup
ORDER BY COUNT(e.EventID) DESC;
