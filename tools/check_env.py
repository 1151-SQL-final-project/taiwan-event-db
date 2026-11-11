"""Demo 電腦環境檢查：在要 Demo 的電腦上跑一次，確認每一項都是 ✓。

用法（在專案根目錄；還沒建虛擬環境也能跑）：
    python tools\\check_env.py
    .venv\\Scripts\\python tools\\check_env.py      # 建好虛擬環境後再跑一次，會多檢查套件與資料庫

只用 Python 內建模組，不會修改任何設定。每個 ✗ 後面都有建議的解決方法。
"""
import importlib
import pathlib
import platform
import socket
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
problems = 0


def report(ok, name, detail="", fix=""):
    global problems
    mark = "✓" if ok else ("！" if ok is None else "✗")
    print(f" {mark} {name}" + (f"：{detail}" if detail else ""))
    if not ok and fix:
        print(f"     → {fix}")
    if ok is False:
        problems += 1


def office_bitness():
    import winreg
    for path in [r"SOFTWARE\Microsoft\Office\ClickToRun\Configuration"]:
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
                return {"x64": 64, "x86": 32}.get(winreg.QueryValueEx(key, "Platform")[0])
        except OSError:
            pass
    for version in ["16.0", "15.0", "14.0"]:
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\Office\{version}\Outlook",
                                    0, winreg.KEY_READ | view) as key:
                    return {"x64": 64, "x86": 32}.get(winreg.QueryValueEx(key, "Bitness")[0])
            except OSError:
                pass
    return None


def com_registered(prog_id):
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id).Close()
        return True
    except OSError:
        return False


def main():
    print("【系統】")
    report(platform.system() == "Windows", "作業系統", platform.platform(), "本專案需要 Windows（Access 只有 Windows 版）")
    py_bits = struct.calcsize("P") * 8
    report(sys.version_info >= (3, 10), "Python 版本", platform.python_version(), "請安裝 Python 3.12（python.org）")
    office = office_bitness()
    report(office is not None, "Office 位元數", f"{office} 位元" if office else "找不到", "請安裝 Microsoft Office（含 Access）")
    report(office is None or office == py_bits, "Python 與 Office 位元數一致", f"Python {py_bits} 位元／Office {office} 位元",
           f"請改裝 {office} 位元的 Python，否則連不上 Access 資料庫")

    print("【Access 元件】")
    report(com_registered("Access.Application"), "Microsoft Access", "", "請安裝含 Access 的 Office 版本")
    report(com_registered("DAO.DBEngine.120"), "DAO 資料庫引擎（建資料庫用）", "",
           "請安裝 Microsoft Access Database Engine（與 Office 同位元數）")
    try:
        import pyodbc
        drivers = [d for d in pyodbc.drivers() if "accdb" in d.lower()]
        report(bool(drivers), "Access ODBC 驅動程式（網頁後端用）", "、".join(drivers) or "沒有",
               "請安裝 Microsoft Access Database Engine（與 Python 同位元數）")
    except ImportError:
        report(None, "Access ODBC 驅動程式", "還沒裝 pyodbc，建好虛擬環境後再跑一次")

    print("【專案】")
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    report(venv.exists(), "虛擬環境 .venv", "", "python -m venv .venv，再 .venv\\Scripts\\python -m pip install -r requirements.txt")
    for module in ["fastapi", "uvicorn", "pyodbc", "win32com.client", "esprima"]:
        try:
            importlib.import_module(module)
            report(True, f"套件 {module}")
        except ImportError:
            report(None if not sys.prefix.endswith(".venv") else False, f"套件 {module}", "未安裝",
                   ".venv\\Scripts\\python -m pip install -r requirements.txt")
    db = ROOT / "db" / "events.accdb"
    report(db.exists(), "資料庫 db\\events.accdb", "", ".venv\\Scripts\\python db\\build_db.py --with-test-events")
    if db.exists():
        try:
            import pyodbc
            conn = pyodbc.connect("DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + str(db))
            count = conn.cursor().execute("SELECT COUNT(*) FROM EventTable").fetchone()[0]
            conn.close()
            report(True, "連得上資料庫", f"活動 {count} 筆")
        except Exception as exc:
            report(False, "連得上資料庫", str(exc)[:120], "多半是位元數不一致或沒有 ODBC 驅動程式（見上面）")
    report((ROOT / "db" / "後台.accdb").exists(), "Access 管理後台 db\\後台.accdb", "",
           ".venv\\Scripts\\python db\\build_admin_frontend.py（執行前先關閉 Access）")

    print("【Demo】")
    with socket.socket() as s:
        free = s.connect_ex(("127.0.0.1", 8000)) != 0
    report(free, "連接埠 8000 沒被佔用", "", "已經有程式在用 8000：關掉它，或啟動時加 --port 8001")
    edge = subprocess.run(["where", "msedge"], capture_output=True, shell=True).returncode == 0 or any(
        p.exists() for p in [pathlib.Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                             pathlib.Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe")])
    report(edge, "瀏覽器 Edge", "", "任何新版瀏覽器都可以，自動測試才需要 Edge")

    print("\n" + ("全部正常，可以 Demo。" if problems == 0 else f"有 {problems} 個問題，請依 → 的說明處理。"))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
