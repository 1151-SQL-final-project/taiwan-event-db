"""自動測試用的資料庫：正式的 events.accdb 沒有（測試）活動，測試前另外建一個有的。

（測試）活動的日期是從建立當天往前後推算的（例如「兩天後中午開賣」），所以每次測試都重建，結果才不會隨日期改變。
"""
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def build(path: pathlib.Path) -> pathlib.Path:
    """在 path 建立「真實資料＋（測試）活動」的資料庫（約 1 分鐘）。"""
    print("建立測試用資料庫（含（測試）活動）…", flush=True)
    subprocess.run([sys.executable, str(ROOT / "db" / "build_db.py"), "--with-test-events", "--out", str(path)],
                   check=True, stdout=subprocess.DEVNULL)
    return path
