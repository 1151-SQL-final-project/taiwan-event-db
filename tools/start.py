"""一鍵啟動探點：由專題資料夾的「啟動探點.bat」（或桌面捷徑）執行，不用自己打指令。

依序做這些事，已經做過的會跳過：
1. 第一次執行：建立虛擬環境 .venv 並安裝執行需要的套件（約 1–2 分鐘，需要網路）
2. 第一次執行：產生資料庫 db\\events.accdb（約 1 分鐘）
3. 啟動網站，等網站準備好後自動用瀏覽器打開；關掉這個視窗就會停止網站
   如果 8000 已經有探點在跑（例如重複點了捷徑），就直接打開瀏覽器

另外：
    python tools\\start.py --shortcut     在桌面建立「探點」捷徑（建立桌面捷徑.bat 就是執行這個）
    python tools\\start.py --port 8001    改用其他連接埠
只用 Python 內建模組，還沒建虛擬環境時也能執行。
"""
import argparse
import base64
import json
import pathlib
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

ROOT = pathlib.Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
DB_FILE = ROOT / "db" / "events.accdb"
ICON = ROOT / "tools" / "tandian.ico"


def step(message):
    print(f"\n▶ {message}", flush=True)


def stop(message, fix=""):
    print(f"\n✗ {message}")
    if fix:
        print(f"  → {fix}")
    print("  也可以執行 python tools\\check_env.py 檢查環境（說明見 docs\\setup-guide.md）。")
    sys.exit(1)


def run(args, error, fix=""):
    if subprocess.run(args, cwd=ROOT).returncode != 0:
        stop(error, fix)


def runtime_requirements() -> list[str]:
    """requirements.txt 裡執行網站需要的套件（「以下只有跑測試才需要」之後的不裝，省時間）。"""
    packages = []
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        if "只有跑測試才需要" in line:
            break
        line = line.split("#")[0].strip()
        if line:
            packages.append(line)
    return packages


def in_venv() -> bool:
    return pathlib.Path(sys.prefix).resolve() == (ROOT / ".venv").resolve()


def ensure_venv():
    """還沒有虛擬環境就建立並安裝套件，然後改用虛擬環境的 Python 重新執行本程式。"""
    if in_venv():
        return
    if not VENV_PYTHON.exists():
        if sys.version_info < (3, 10):
            stop(f"Python 版本太舊（{sys.version.split()[0]}）", "請安裝 Python 3.12（python.org），安裝時勾選 Add python.exe to PATH")
        step("第一次執行：建立虛擬環境並安裝套件（約 1–2 分鐘，需要網路）")
        run([sys.executable, "-m", "venv", str(ROOT / ".venv")], "建立虛擬環境失敗")
        run([str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", *runtime_requirements()],
            "安裝套件失敗", "請確認有網路，再重新執行")
    # Windows 的 os.execv 不會真的取代目前的程式，改用子程式執行並等它結束
    sys.exit(subprocess.run([str(VENV_PYTHON), str(pathlib.Path(__file__).resolve()), *sys.argv[1:]]).returncode)


def ensure_database():
    if DB_FILE.exists():
        return
    import pyodbc  # 虛擬環境裡才有
    if not any("accdb" in d.lower() for d in pyodbc.drivers()):
        bits = 64 if sys.maxsize > 2**32 else 32
        stop("找不到 Access 資料庫驅動程式",
             f"請安裝 Microsoft Access Database Engine 2016（{bits} 位元，要和 Python 相同），或含 Access 的 Office")
    step("第一次執行：產生資料庫（約 1 分鐘）")
    run([sys.executable, str(ROOT / "db" / "build_db.py")], "產生資料庫失敗",
        "多半是 Python 和 Office 的位元數不一致；若 Access 正開著 events.accdb，請先關掉")


def tandian_running(port: int) -> bool:
    """這個連接埠上是不是已經有探點在跑（看 /api/health 的回應）。"""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
            return "database" in json.loads(r.read().decode("utf-8"))
    except Exception:  # noqa: BLE001  連不上、不是探點都算沒有
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def open_when_ready(url: str):
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=2)
            webbrowser.open(url)
            print(f"\n✓ 已用瀏覽器打開 {url}（沒有自動打開的話，請自己貼到瀏覽器）")
            print("  Demo 期間請不要關掉這個視窗；關掉視窗就會停止網站。\n", flush=True)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    print(f"\n網站一分鐘內沒有回應，請看上面的訊息；也可以自己打開 {url}")


def serve(port: int, browser: bool):
    url = f"http://127.0.0.1:{port}/"
    if tandian_running(port):
        print(f"\n✓ 探點已經在 {url} 執行中，直接打開瀏覽器")
        if browser:
            webbrowser.open(url)
        return
    if not port_free(port):
        stop(f"連接埠 {port} 被其他程式佔用", f"關掉那個程式，或改用其他連接埠：python tools\\start.py --port {port + 1}")
    step(f"啟動網站 {url}")
    if browser:
        threading.Thread(target=open_when_ready, args=(url,), daemon=True).start()
    try:
        subprocess.run([sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "api", "--port", str(port)], cwd=ROOT)
    except KeyboardInterrupt:
        pass


def make_shortcut():
    """在桌面建立「探點」捷徑，指向專題資料夾的 啟動探點.bat。
    用 PowerShell 的 WScript.Shell 建立；指令用 -EncodedCommand 傳，路徑有中文或空格也沒問題。"""
    target = ROOT / "啟動探點.bat"
    q = lambda s: "'" + str(s).replace("'", "''") + "'"  # PowerShell 單引號字串
    script = (
        "[Console]::OutputEncoding = [Text.Encoding]::UTF8; "
        "$shell = New-Object -ComObject WScript.Shell; "
        "$path = Join-Path $shell.SpecialFolders('Desktop') '探點.lnk'; "
        "$s = $shell.CreateShortcut($path); "
        f"$s.TargetPath = {q(target)}; $s.WorkingDirectory = {q(ROOT)}; "
        f"$s.IconLocation = {q(ICON)}; $s.Description = '啟動探點網站並打開瀏覽器'; "
        "$s.Save(); Write-Output $path"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode()
    result = subprocess.run(["powershell", "-NoProfile", "-EncodedCommand", encoded], capture_output=True)
    path = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode != 0:
        stop("建立捷徑失敗", result.stderr.decode("utf-8", "replace").strip()[:200])
    print(f"✓ 已在桌面建立捷徑：{path}")
    print("  之後雙擊桌面上的「探點」就會啟動網站。專題資料夾搬家後要重新建立一次。")


def main():
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="一鍵啟動探點")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="不要自動打開瀏覽器")
    parser.add_argument("--shortcut", action="store_true", help="在桌面建立捷徑")
    args = parser.parse_args()
    if args.shortcut:
        make_shortcut()
        return
    print(f"探點｜專題資料夾：{ROOT}")
    ensure_venv()
    ensure_database()
    serve(args.port, not args.no_browser)


if __name__ == "__main__":
    main()
