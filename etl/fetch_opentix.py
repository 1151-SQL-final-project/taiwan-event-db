"""ETL 補充資料：下載文化部活動資料中、連到 OPENTIX 的活動頁，用來補票價與優惠。

用法（在專案根目錄，先跑過 etl\\clean_moc.py）：
    .venv\\Scripts\\python etl\\fetch_opentix.py

- 每秒最多 1 個請求，避免造成對方伺服器負擔；OPENTIX 的 robots.txt 允許爬取（Allow: /）。
- 下載的網頁壓縮後存在 data/raw/opentix/（不上傳 git），已下載過的會跳過，中斷後重跑會接著下載。
- 只取活動頁上公開的票價與優惠方案，每筆資料都記錄來源網址。
"""
import csv
import gzip
import pathlib
import re
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "raw" / "opentix"
USER_AGENT = "Mozilla/5.0 (compatible; taiwan-event-db student project; NTNU SQL course)"
# 文化部資料裡大多是 /program/編號，會轉址到同編號的 /event/編號
URL_RE = re.compile(r"https://www\.opentix\.life/(?:program|event)/(\d+)")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (ROOT / "data" / "clean" / "moc_events.csv").open(encoding="utf-8-sig") as f:
        ids = list(dict.fromkeys(m.group(1) for row in csv.DictReader(f) if (m := URL_RE.search(row["EventURL"]))))
    todo = [i for i in ids if not (OUT_DIR / f"{i}.html.gz").exists()]
    print(f"OPENTIX 活動頁 {len(ids)} 個，需下載 {len(todo)} 個", flush=True)
    failed = 0
    for n, event_id in enumerate(todo, 1):
        started = time.time()
        req = urllib.request.Request(f"https://www.opentix.life/event/{event_id}", headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                (OUT_DIR / f"{event_id}.html.gz").write_bytes(gzip.compress(resp.read()))
        except Exception as exc:
            failed += 1
            print(f"  失敗 {event_id}：{exc}", flush=True)
        if n % 50 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(max(0.0, 1.0 - (time.time() - started)))
    print(f"完成，失敗 {failed} 個", flush=True)


if __name__ == "__main__":
    main()
