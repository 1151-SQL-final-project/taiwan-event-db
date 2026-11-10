-- 商家上架活動：一律是「待審核」，管理員通過後才會公開；資料來源填「商家上架」
INSERT INTO EventTable (EventCategory_FK, EventVenue_FK, EventTitle, EventStartDate, EventEndDate,
                        EventOriginalPrice, EventURL, EventDataSource, EventOrganizer_FK, EventStatus, EventDescription,
                        EventSaleStartDate, EventImageURL)
VALUES ([@category_id], [@venue_id], [@title], [@start_date], [@end_date],
        [@price], [@url], '商家上架', [@organizer_id], '待審核', [@description], [@sale_start], [@image_url]);
