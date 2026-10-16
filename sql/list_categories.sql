-- 活動類別清單（搜尋頁的下拉選單）；CategoryGroup 用來一次查「學習類」或「休閒類」
SELECT CategoryID, CategoryName, CategoryGroup
FROM CategoryTable
ORDER BY CategoryID;
