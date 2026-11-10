-- 下架前先預覽：已經結束、但狀態還是「上架中」的活動
SELECT EventID, EventTitle, EventEndDate
FROM EventTable
WHERE EventStatus = '上架中' AND EventEndDate < Date()
ORDER BY EventEndDate;
