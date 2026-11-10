-- 自動下架：已經結束（結束日早於今天）但還是「上架中」的活動，改成「已下架」。資料不刪除，收藏紀錄也保留
-- Access 沒有排程，所以由後端在伺服器啟動、打開商家或管理員後台時執行
UPDATE EventTable
SET EventStatus = '已下架'
WHERE EventStatus = '上架中' AND EventEndDate < Date();
