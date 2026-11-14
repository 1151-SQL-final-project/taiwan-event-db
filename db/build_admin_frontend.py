"""產生 Access 管理後台 db/後台.accdb（前端），連結 db/events.accdb（後端）的資料表。

用法（在專案根目錄，先跑過 db\\build_db.py；執行前請關閉 Access）：
    .venv\\Scripts\\python db\\build_admin_frontend.py

產生的內容：
    連結資料表   events.accdb 的 8 張資料表（資料存在後端，前端只放表單）
    查詢         從後端匯入 統計_、管理_、提醒_ 開頭的查詢
    表單         主選單（開啟時自動顯示）、活動管理（含優惠子表單）、場館管理、類別管理、優惠類型管理
    VBA          主選單按鈕的程式，包含「一鍵下架」（先顯示會下架幾場、確認後才執行）

網頁的管理員後台（審核、違規下架、統計）是主要的管理介面；這個 Access 後台是給管理員
直接在 Access 裡維護資料用的（也用來在期末報告示範 Access 表單）。

為什麼分前後端：build_db.py 每次會重建 events.accdb，表單放在另一個檔案才不會被清掉。
步驟說明見 docs/access-form-guide.md（這支程式做的事和文件中的手動步驟相同）。
"""
import pathlib
import sys

import win32com.client

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT / "db" / "events.accdb"
FRONTEND = ROOT / "db" / "後台.accdb"

# Access 常數
AC_FORM, AC_TABLE, AC_QUERY = 2, 0, 1
AC_LINK, AC_IMPORT = 2, 0
AC_LABEL, AC_TEXTBOX, AC_COMMAND, AC_COMBO, AC_CHECKBOX, AC_SUBFORM = 100, 109, 104, 111, 106, 112
AC_DETAIL, AC_HEADER = 0, 1
AC_SAVE_YES = 1
VIEW_SINGLE, VIEW_DATASHEET = 0, 2
TWIP = 1440  # 1 英吋

TABLES = ["CityTable", "CategoryTable", "DiscountTypeTable", "UserTable", "VenueTable", "EventTable",
          "DiscountTable", "SaveTable"]
LOOKUPS = {  # 外鍵欄位 → 下拉選單的資料來源
    "EventCategory_FK": "SELECT CategoryID, CategoryName FROM CategoryTable ORDER BY CategoryID",
    "EventVenue_FK": "SELECT VenueID, VenueName FROM VenueTable ORDER BY VenueName",
    # 上架者只能是商家或管理員（開放資料匯入的活動掛在管理員帳號下）
    "EventOrganizer_FK": "SELECT UserID, UserName FROM UserTable WHERE UserRole IN ('商家', '管理員') ORDER BY UserID",
    "DiscountType_FK": "SELECT DiscountTypeID, DiscountTypeName FROM DiscountTypeTable ORDER BY DiscountTypeID",
    "VenueCity_FK": "SELECT CityID, CityName FROM CityTable ORDER BY CityID",
}
VALUE_LISTS = {  # 固定選項的欄位 → 下拉選單（值清單）
    "EventStatus": '"待審核";"上架中";"已退回";"已下架"',
    "CategoryGroup": '"學習類";"休閒類"',
}


class Builder:
    """注意：在 Rename 之後再 CreateForm 會讓 Access 當掉（實測），
    所以先用暫時名稱建好所有表單，最後才一次改名（finish_renames）。"""

    def __init__(self, app):
        self.app = app
        self.renames: list[tuple[str, str]] = []  # (暫時名稱, 正式名稱)

    def new_form(self, record_source: str | None, caption: str, view: int):
        form = self.app.CreateForm()
        if record_source:
            form.RecordSource = record_source
        form.Caption = caption
        form.DefaultView = view
        form.AllowDatasheetView = True
        return form

    def field(self, form, column: str, label: str, left: int, top: int, width: int, height: int = 360,
              section: int = AC_DETAIL, with_label: bool = True):
        """在表單上放一個綁定欄位的控制項（外鍵用下拉選單、是/否用核取方塊）。"""
        kind = AC_COMBO if column in LOOKUPS or column in VALUE_LISTS else AC_TEXTBOX
        ctl = self.app.CreateControl(form.Name, kind, section, "", column, left, top, width, height)
        ctl.Name = label  # 資料工作表的欄位標題會用控制項名稱
        if column in LOOKUPS:
            ctl.RowSource = LOOKUPS[column]
            ctl.ColumnCount = 2
            ctl.ColumnWidths = f"0;{width}"
            ctl.BoundColumn = 1
            ctl.LimitToList = True
        elif column in VALUE_LISTS:
            ctl.RowSourceType = "Value List"
            ctl.RowSource = VALUE_LISTS[column]
            ctl.LimitToList = True
        if with_label and form.DefaultView != VIEW_DATASHEET:
            lbl = self.app.CreateControl(form.Name, AC_LABEL, section, "", "", left - 1700, top, 1600, height)
            lbl.Caption = label
            lbl.TextAlign = 3  # 靠右
        return ctl

    def save(self, form, name: str) -> str:
        temp = form.Name
        self.app.DoCmd.Close(AC_FORM, temp, AC_SAVE_YES)
        self.renames.append((temp, name))
        return temp

    def finish_renames(self):
        for temp, name in self.renames:
            self.app.DoCmd.Rename(name, AC_FORM, temp)


def build(app):
    b = Builder(app)

    # 1. 連結資料表、匯入查詢
    for table in TABLES:
        app.DoCmd.TransferDatabase(AC_LINK, "Microsoft Access", str(BACKEND), AC_TABLE, table, table)
    backend = app.DBEngine.OpenDatabase(str(BACKEND))
    queries = [backend.QueryDefs(i).Name for i in range(backend.QueryDefs.Count)]
    backend.Close()
    for name in queries:
        if name.startswith(("統計_", "管理_", "提醒_")):
            app.DoCmd.TransferDatabase(AC_IMPORT, "Microsoft Access", str(BACKEND), AC_QUERY, name, name)

    # 2. 子表單（資料工作表）
    form = b.new_form("DiscountTable", "優惠", VIEW_DATASHEET)
    for i, (col, label, width) in enumerate([("DiscountType_FK", "優惠類型", 1300), ("DiscountPrice", "優惠價", 900),
                                             ("DiscountDescription", "說明", 3600), ("DiscountStartDate", "開始日期", 1300),
                                             ("DiscountEndDate", "截止日期", 1300)]):
        b.field(form, col, label, 200, 200 + i * 450, width).ColumnWidth = width
    b.save(form, "優惠_子表單")

    # 3. 活動管理（單筆表單＋優惠子表單）
    form = b.new_form("SELECT * FROM EventTable ORDER BY EventID DESC", "活動管理", VIEW_SINGLE)
    form.Width = int(9.6 * TWIP)
    left, top = 1900, 200
    rows = [("EventID", "活動編號", 1200), ("EventTitle", "活動名稱", 7200), ("EventCategory_FK", "類別", 2400),
            ("EventVenue_FK", "場館", 5000), ("EventStartDate", "開始日期", 1800), ("EventEndDate", "結束日期", 1800),
            ("EventOriginalPrice", "全票價格", 1800), ("EventURL", "官方網址", 7200),
            ("EventDataSource", "資料來源", 4000), ("EventOrganizer_FK", "上架商家", 3000), ("EventStatus", "審核狀態", 1800),
            ("EventSaleStartDate", "開賣時間", 2400), ("EventRejectReason", "退回理由", 7200)]
    for col, label, width in rows:
        ctl = b.field(form, col, label, left, top, width)
        if col == "EventID":
            ctl.Locked, ctl.Enabled = True, False
        top += 440
    desc = b.field(form, "EventDescription", "活動說明", left, top, 7200, 1300)
    desc.ScrollBars = 2
    top += 1450
    for title, child, height in [("優惠", "DiscountEvent_FK", 2400)]:
        lbl = app.CreateControl(form.Name, AC_LABEL, AC_DETAIL, "", "", 200, top, 1600, 360)
        lbl.Caption, lbl.FontBold = title, True
        sub = app.CreateControl(form.Name, AC_SUBFORM, AC_DETAIL, "", "", left, top, int(7.6 * TWIP), height)
        sub.LinkMasterFields, sub.LinkChildFields = "EventID", child
        sub.Name = f"{title}子表單"  # 子表單來源等改名完成後再設定
        top += height + 200
    b.save(form, "活動管理")

    # 4. 場館、類別、優惠類型（資料工作表）
    for source, caption, cols in [
        ("VenueTable", "場館管理", [("VenueName", "場館名稱", 3600), ("VenueCity_FK", "縣市", 1300), ("VenueAddress", "地址", 5000)]),
        ("CategoryTable", "類別管理", [("CategoryName", "類別名稱", 2400), ("CategoryGroup", "類別分組", 1600)]),
        ("DiscountTypeTable", "優惠類型管理", [("DiscountTypeName", "優惠類型名稱", 2400)]),
    ]:
        form = b.new_form(source, caption, VIEW_DATASHEET)
        for i, (col, label, width) in enumerate(cols):
            b.field(form, col, label, 200, 200 + i * 450, width).ColumnWidth = width
        b.save(form, caption)

    # 5. 主選單
    form = b.new_form(None, "探點 管理後台", VIEW_SINGLE)
    form.RecordSelectors, form.NavigationButtons, form.DividingLines = False, False, False
    form.Width = int(6.6 * TWIP)
    title = app.CreateControl(form.Name, AC_LABEL, AC_DETAIL, "", "", 300, 200, int(6 * TWIP), 600)
    title.Caption, title.FontSize, title.FontBold = "探點　管理後台", 16, True
    buttons = [  # (名稱, 標題, 欄, 列)
        ("btnEvents", "活動管理", 0, 0), ("btnVenues", "場館管理", 1, 0),
        ("btnCategories", "類別管理", 0, 1), ("btnDiscountTypes", "優惠類型管理", 1, 1),
        ("btnPending", "待審核活動", 0, 2), ("btnStatsStatus", "各審核狀態活動數", 1, 2),
        ("btnStatsRegion", "各地區活動數", 0, 3), ("btnStatsCategory", "各類別活動數", 1, 3),
        ("btnPopular", "熱門收藏排行", 0, 4), ("btnEarlyBird", "早鳥即將截止", 1, 4),
        ("btnPreview", "預覽待下架活動", 0, 5), ("btnDeactivate", "一鍵下架已結束活動", 1, 5),
        ("btnExpiredDiscounts", "刪除過期優惠", 0, 6),
    ]
    for name, caption, col, row in buttons:
        btn = app.CreateControl(form.Name, AC_COMMAND, AC_DETAIL, "", "", 300 + col * int(3.1 * TWIP),
                                1100 + row * 620, int(2.9 * TWIP), 480)
        btn.Name, btn.Caption, btn.OnClick = name, caption, "[Event Procedure]"
        if name == "btnDeactivate":
            btn.FontBold = True
    note = app.CreateControl(form.Name, AC_LABEL, AC_DETAIL, "", "", 300, 1100 + 7 * 620 + 100, int(6 * TWIP), 600)
    note.Caption = "資料存在 events.accdb；網頁與這個後台使用同一份資料。審核商家活動請用網頁的管理員後台。"
    note.ForeColor = 8421504
    form.HasModule = True
    form.Module.AddFromString(MENU_VBA)
    b.save(form, "主選單")

    # 6. 所有表單改成正式名稱，再把子表單接上
    b.finish_renames()
    app.DoCmd.OpenForm("活動管理", 1)  # acDesign
    main_form = app.Forms("活動管理")
    for control, source in [("優惠子表單", "優惠_子表單")]:
        main_form.Controls(control).SourceObject = f"Form.{source}"
    app.DoCmd.Close(AC_FORM, "活動管理", AC_SAVE_YES)

    # 7. 標準模組 modAdmin（一鍵下架）
    module_file = FRONTEND.with_name("_modAdmin.bas")
    module_file.write_bytes(MODULE_VBA.replace("\n", "\r\n").encode("cp950"))
    try:
        app.LoadFromText(5, "modAdmin", str(module_file))  # acModule
    finally:
        module_file.unlink()

    # 8. 開啟檔案時自動顯示主選單
    db = app.CurrentDb()
    for prop, value in [("StartupForm", "主選單"), ("AppTitle", "探點 管理後台")]:
        try:
            db.Properties(prop).Value = value
        except Exception:
            db.Properties.Append(db.CreateProperty(prop, 10, value))


MENU_VBA = r'''
Option Explicit

Private Sub btnEvents_Click()
    DoCmd.OpenForm "活動管理"
End Sub

Private Sub btnVenues_Click()
    DoCmd.OpenForm "場館管理"
End Sub

Private Sub btnCategories_Click()
    DoCmd.OpenForm "類別管理"
End Sub

Private Sub btnDiscountTypes_Click()
    DoCmd.OpenForm "優惠類型管理"
End Sub

Private Sub btnPending_Click()
    DoCmd.OpenQuery "管理_待審核活動"
End Sub

Private Sub btnStatsStatus_Click()
    DoCmd.OpenQuery "統計_各審核狀態活動數"
End Sub

Private Sub btnStatsRegion_Click()
    DoCmd.OpenQuery "統計_各地區活動數"
End Sub

Private Sub btnStatsCategory_Click()
    DoCmd.OpenQuery "統計_各類別活動數"
End Sub

Private Sub btnPopular_Click()
    DoCmd.OpenQuery "統計_熱門收藏排行"
End Sub

Private Sub btnEarlyBird_Click()
    DoCmd.OpenQuery "提醒_早鳥即將截止"
End Sub

Private Sub btnPreview_Click()
    DoCmd.OpenQuery "管理_預覽待下架活動"
End Sub

Private Sub btnDeactivate_Click()
    DeactivateEnded True
End Sub

Private Sub btnExpiredDiscounts_Click()
    Dim n As Long
    n = DCount("*", "DiscountTable", "DiscountEndDate < Date()")
    If n = 0 Then
        MsgBox "目前沒有過期的優惠。", vbInformation, "刪除過期優惠"
    ElseIf MsgBox("有 " & n & " 筆優惠已經過了截止日期，確定要刪除嗎？" & vbCrLf & _
                  "（沒有截止日期的優惠不會被刪除）", vbYesNo + vbExclamation, "刪除過期優惠") = vbYes Then
        CurrentDb.Execute "管理_刪除過期優惠", dbFailOnError
        MsgBox "已刪除 " & n & " 筆過期優惠。", vbInformation, "刪除過期優惠"
    End If
End Sub
'''

# 標準模組：一鍵下架的邏輯放這裡，按鈕和其他程式（例如測試用的 Eval）都能呼叫。
# 用 LoadFromText 載入，不需要開啟「信任存取 VBA 專案物件模型」；檔案必須是 Big5（cp950）編碼。
MODULE_VBA = r'''Option Compare Database
Option Explicit

' 一鍵下架：把結束日早於今天、還在上架中的活動改成「已下架」（資料不刪除）。
' askFirst = True 時先顯示會下架幾場並請使用者確認；回傳下架的筆數。
Public Function DeactivateEnded(ByVal askFirst As Boolean) As Long
    Dim n As Long
    n = DCount("*", "EventTable", "EventEndDate < Date() AND EventStatus = '上架中'")
    If n = 0 Then
        If askFirst Then MsgBox "目前沒有需要下架的活動。", vbInformation, "一鍵下架"
        Exit Function
    End If
    If askFirst Then
        If MsgBox("有 " & n & " 場活動已經結束但還在上架中，確定要全部下架嗎？" & vbCrLf & _
                  "（資料不會刪除，之後可以重新上架）", vbYesNo + vbQuestion, "一鍵下架") <> vbYes Then Exit Function
    End If
    CurrentDb.Execute "管理_一鍵下架已結束活動", dbFailOnError
    DeactivateEnded = n
    If askFirst Then MsgBox "已下架 " & n & " 場活動。", vbInformation, "一鍵下架"
End Function
'''


TRUST_KEY = r"Software\Microsoft\Office\16.0\Access\Security\Trusted Locations"


def set_trusted_location(name: str, folder: pathlib.Path, description: str):
    """把資料夾加進 Access 的「信任位置」（只影響目前的 Windows 使用者、不含子資料夾）。
    不在信任位置的檔案，VBA 會被停用，主選單的按鈕要先按「啟用內容」才能用。
    移除方法：Access →「檔案」→「選項」→「信任中心」→「信任中心設定」→「信任位置」→ 選取 → 移除。"""
    import datetime as dt
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{TRUST_KEY}\\{name}") as key:
        winreg.SetValueEx(key, "Path", 0, winreg.REG_SZ, str(folder) + "\\")
        winreg.SetValueEx(key, "AllowSubfolders", 0, winreg.REG_DWORD, 0)
        winreg.SetValueEx(key, "Description", 0, winreg.REG_SZ, description)
        winreg.SetValueEx(key, "Date", 0, winreg.REG_SZ, dt.datetime.now().strftime("%Y/%m/%d %H:%M"))


def remove_trusted_location(name: str):
    import winreg
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, f"{TRUST_KEY}\\{name}")
    except FileNotFoundError:
        pass


def main():
    if "--no-trust" not in sys.argv:
        set_trusted_location("TaiwanEventDB", FRONTEND.parent, "探點 管理後台")
        print(f"已將 {FRONTEND.parent} 加入 Access 信任位置（不想要的話加上 --no-trust 參數重跑，並到信任中心移除）")
    if not BACKEND.exists():
        sys.exit("找不到 db/events.accdb，請先執行 db\\build_db.py")
    if FRONTEND.exists():
        FRONTEND.unlink()  # 若 Access 正開著這個檔案會失敗，請先關掉
    app = win32com.client.DispatchEx("Access.Application")
    app.Visible = False
    try:
        app.NewCurrentDatabase(str(FRONTEND))
        build(app)
        app.CloseCurrentDatabase()
    finally:
        app.Quit()
    print(f"已建立 {FRONTEND}")


if __name__ == "__main__":
    main()
