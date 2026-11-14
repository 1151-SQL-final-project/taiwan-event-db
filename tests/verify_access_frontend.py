"""驗證 Access 管理後台（db/後台.accdb）：表單能開、優惠子表單有連動、下拉選單、一鍵下架有效，
並在 Access 開著表單的同時，讓網頁後端讀寫同一個資料庫（確認可以同時使用）。

用法（在專案根目錄，先跑過 db\\build_db.py 與 db\\build_admin_frontend.py；執行前請關閉 Access）：
    .venv\\Scripts\\python tests\\verify_access_frontend.py

- 後端另外建一個含（測試）活動的 db/_test_events.accdb，前端複製成 db/_test_後台.accdb 再測（測完刪除），正式資料不會被修改。
- 測試時 Access 視窗會短暫出現，截圖存在 tests/screenshots/。
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid

import test_db

import win32com.client
import win32con
import win32gui
from PIL import ImageGrab

import ctypes
import gc

ctypes.windll.user32.SetProcessDPIAware()  # 螢幕有縮放（125%、150%）時，截圖座標才會正確

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
PORT = 8768
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("  ✓ " if ok else "  ✗ ") + name + (f"（{detail}）" if detail else ""), flush=True)


def screenshot(app, name):
    hwnd = app.hWndAccessApp()
    win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(1.5)
    ImageGrab.grab(bbox=win32gui.GetWindowRect(hwnd)).save(SHOTS / name)


def api(path, body=None, token=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method="POST" if body is not None else "GET",
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status, json.loads(resp.read() or b"null")


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    # 測試用的複本放在 db\ 裡（build_admin_frontend.py 已把 db\ 加入 Access 信任位置），
    # VBA（一鍵下架）才會執行；測試結束就刪除。放在其他資料夾的話 VBA 會被停用。
    backend, frontend = ROOT / "db" / "_test_events.accdb", ROOT / "db" / "_test_後台.accdb"
    test_db.build(backend)
    shutil.copy(ROOT / "db" / "後台.accdb", frontend)
    try:
        exercise(backend, frontend)
    finally:
        # Python 手上的 Access 物件都釋放之後，Access 才會真的結束、放開檔案
        gc.collect()
        for path in (backend, frontend, backend.with_suffix(".laccdb"), frontend.with_suffix(".laccdb")):
            for _ in range(60):
                try:
                    path.unlink(missing_ok=True)
                    break
                except PermissionError:
                    time.sleep(0.5)
    print(f"\n{sum(results)}／{len(results)} 項通過" + ("，全部通過" if all(results) else ""))
    sys.exit(0 if all(results) else 1)


def exercise(backend: pathlib.Path, frontend: pathlib.Path):
    app = win32com.client.DispatchEx("Access.Application")
    server = None
    try:
        app.Visible = True
        app.OpenCurrentDatabase(str(frontend))
        # 連結資料表改指向測試用的後端複本。在 Access 裡面改，不另外開 DAO，
        # 否則 Python 的 DAO 會一直鎖住檔案，測完刪不掉
        cdb = app.CurrentDb()
        linked = 0
        for i in range(cdb.TableDefs.Count):
            td = cdb.TableDefs(i)
            if td.Connect:
                td.Connect = f";DATABASE={backend}"
                td.RefreshLink()
                linked += 1
        check("前端有 8 張連結資料表，已改指向測試複本", linked == 8, f"{linked} 張")
        time.sleep(2)
        forms = [app.CurrentProject.AllForms(i).Name for i in range(app.CurrentProject.AllForms.Count)]
        check("6 個表單都在", set(forms) >= {"主選單", "活動管理", "優惠_子表單", "場館管理", "類別管理", "優惠類型管理"},
              "、".join(forms))
        queries = [q.Name for q in app.CurrentDb().QueryDefs if not q.Name.startswith("~")]
        check("統計、管理、提醒查詢都匯入了", len(queries) >= 12, f"{len(queries)} 個")
        check("開啟時自動顯示主選單", app.CurrentProject.AllForms("主選單").IsLoaded)
        screenshot(app, "access_01_menu.png")

        # 活動管理：找一場上架中、還沒結束、有多筆優惠的活動，確認子表單有連動
        db = app.CurrentDb()
        rs = db.OpenRecordset(
            "SELECT TOP 1 e.EventID, e.EventTitle FROM EventTable AS e "
            "WHERE e.EventStatus = '上架中' AND e.EventEndDate >= Date() "
            "AND (SELECT COUNT(*) FROM DiscountTable AS d WHERE d.DiscountEvent_FK = e.EventID) > 1")
        event_id, title = rs.Fields("EventID").Value, rs.Fields("EventTitle").Value
        rs.Close()
        app.DoCmd.OpenForm("活動管理", 0, "", f"EventID = {event_id}")
        form = app.Forms("活動管理")
        discounts = form.Controls("優惠子表單").Form.Recordset.RecordCount
        check("活動管理顯示指定活動", form.Controls("活動名稱").Value == title, title[:20])
        for name in ("類別", "場館", "上架商家"):  # 下拉選單第 2 欄是顯示的名稱
            combo = form.Controls(name)
            check(f"{name}是下拉選單、顯示名稱", combo.ControlType == 111 and bool(combo.Column(1)),
                  f"編號 {combo.Value} → {combo.Column(1)}")
        status = form.Controls("審核狀態")
        check("審核狀態是下拉選單（值清單）", status.ControlType == 111 and status.Value == "上架中"
              and status.ListCount == 4, f"{status.Value}，{status.ListCount} 個選項")
        check("優惠子表單連動", discounts > 1, f"{discounts} 筆")
        screenshot(app, "access_02_event_form.png")
        app.DoCmd.Close(2, "活動管理")

        for name in ["場館管理", "類別管理", "優惠類型管理"]:
            app.DoCmd.OpenForm(name)
            count = app.Forms(name).Recordset.RecordCount
            check(f"{name}可以開啟", count > 0, f"{count} 筆")
            if name == "場館管理":
                screenshot(app, "access_03_venues.png")
            app.DoCmd.Close(2, name)

        # 驗證規則在表單裡也有效：結束日早於開始日
        app.DoCmd.OpenForm("活動管理", 0, "", f"EventID = {event_id}")
        form = app.Forms("活動管理")
        try:
            form.Controls("結束日期").Value = "2000/1/1"
            app.DoCmd.RunCommand(97)  # acCmdSaveRecord
            check("表單擋下錯誤日期", False, "沒有被擋下")
        except Exception as exc:
            message = str(exc)
            check("表單擋下錯誤日期（驗證規則）", "結束日期不能早於開始日期" in message, message[-60:])
        try:
            form.Undo()
        except Exception:
            pass
        app.DoCmd.Close(2, "活動管理", 2)  # acSaveNo

        # 一鍵下架
        ended_listed = "EventEndDate < Date() AND EventStatus = '上架中'"
        before = app.DCount("*", "EventTable", ended_listed)
        # 造兩場「已結束但還在上架」的活動。開始日也要往前移，否則違反「結束日不能早於開始日」；
        # dbFailOnError（128）讓錯誤一定會丟出來，不會被默默略過
        db.Execute("UPDATE EventTable SET EventStartDate = DateAdd('d', -10, Date()), "
                   "EventEndDate = DateAdd('d', -3, Date()), EventStatus = '上架中' "
                   "WHERE EventID IN (SELECT TOP 2 EventID FROM EventTable "
                   f"WHERE EventStatus = '上架中' AND EventID <> {event_id} ORDER BY EventID)", 128)
        pending = app.DCount("*", "EventTable", ended_listed)
        # 呼叫 modAdmin 模組的 DeactivateEnded(False)：和按鈕用同一段程式，只是不跳確認視窗
        done = app.Eval("DeactivateEnded(False)")
        after = app.DCount("*", "EventTable", ended_listed)
        offline = app.DCount("*", "EventTable", "EventEndDate < Date() AND EventStatus = '已下架'")
        check("一鍵下架（改成「已下架」）", pending >= 2 and done == pending and after == 0 and offline >= done,
              f"原有 {before}＋測試 2 → 下架 {done} 場，剩 {after} 場")

        # 同時使用：Access 開著活動管理並修改一筆資料，網頁後端同時讀寫
        app.DoCmd.OpenForm("活動管理", 0, "", f"EventID = {event_id}")
        form = app.Forms("活動管理")
        new_title = f"{title[:60]}（後台修改測試）"
        form.Controls("活動名稱").Value = new_title
        app.DoCmd.RunCommand(97)  # 儲存這筆
        env = {**os.environ, "EVENT_DB_PATH": str(backend)}
        server = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "api", "--port", str(PORT)],
                                  cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                api("/api/health")
                break
            except Exception:
                time.sleep(0.5)
        status, detail = api(f"/api/events/{event_id}")
        check("Access 開著時，網頁讀得到後台剛改的資料", status == 200 and detail["EventTitle"] == new_title)
        status, reg = api("/api/auth/register", {"name": "併用測試", "email": f"co-{uuid.uuid4().hex[:6]}@example.com",
                                                 "password": "password123"})
        token = reg["token"]
        status, _ = api(f"/api/saves/{event_id}", body={}, token=token)
        check("Access 開著時，網頁可以註冊與收藏（寫入）", status == 201)
        app.Forms("活動管理").Requery()
        saves = app.DCount("*", "SaveTable", f"SaveEvent_FK = {event_id}")
        check("網頁新增的收藏，Access 馬上看得到", saves >= 1, f"{saves} 筆")
        app.DoCmd.Close(2, "活動管理", 2)
    finally:
        if server:
            server.terminate()
            server.wait(timeout=10)
        try:
            app.CloseCurrentDatabase()
        except Exception:
            pass
        app.Quit()


if __name__ == "__main__":
    main()
