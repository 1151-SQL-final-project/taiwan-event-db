-- 審核與下架：通過（上架中）、退回（已退回）、違規下架（已下架）、重新上架（上架中）
-- 哪些狀態可以改成哪些狀態，由後端檢查（例如已結束的活動不能重新上架）
-- 退回時一起記下理由；改成其他狀態時理由填空值（資料表驗證規則：只有已退回的活動才有退回理由）
UPDATE EventTable
SET EventStatus = [@status], EventRejectReason = [@reason]
WHERE EventID = [@event_id];
