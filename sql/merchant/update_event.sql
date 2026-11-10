-- 商家修改自己的活動：只能改自己上架的（WHERE 同時比對商家編號），改完回到「待審核」重新審核，
-- 之前被退回的理由也一起清掉
UPDATE EventTable
SET EventCategory_FK = [@category_id], EventVenue_FK = [@venue_id], EventTitle = [@title],
    EventStartDate = [@start_date], EventEndDate = [@end_date], EventOriginalPrice = [@price],
    EventURL = [@url], EventDescription = [@description], EventSaleStartDate = [@sale_start], EventImageURL = [@image_url],
    EventStatus = '待審核', EventRejectReason = Null
WHERE EventID = [@event_id] AND EventOrganizer_FK = [@organizer_id];
