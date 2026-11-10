-- 重新上架某一場活動並修改結束日（例如活動延期）
UPDATE EventTable
SET EventStatus = '上架中', EventEndDate = [@new_end_date]
WHERE EventID = [@event_id];
