-- 新增場館（商家、管理員都可以新增）
INSERT INTO VenueTable (VenueName, VenueCity_FK, VenueAddress)
VALUES ([@name], [@city_id], [@address]);
