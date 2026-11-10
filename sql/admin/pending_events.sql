-- 待審核的活動（商家新增或修改後送出的），最早送出的排前面
SELECT e.EventID, e.EventTitle, e.EventStartDate, e.EventEndDate, u.UserName AS OrganizerName
FROM EventTable AS e
INNER JOIN UserTable AS u ON e.EventOrganizer_FK = u.UserID
WHERE e.EventStatus = '待審核'
ORDER BY e.EventID;
