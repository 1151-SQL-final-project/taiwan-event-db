-- 管理員手動新增活動（例如補建開放資料沒有的活動）：上架者填管理員自己，直接上架
INSERT INTO EventTable (EventCategory_FK, EventVenue_FK, EventTitle, EventStartDate, EventEndDate,
                        EventOriginalPrice, EventURL, EventDataSource, EventOrganizer_FK, EventStatus, EventDescription)
VALUES ([@category_id], [@venue_id], [@title], [@start_date], [@end_date],
        [@price], [@url], [@data_source], [@organizer_id], '上架中', [@description]);
