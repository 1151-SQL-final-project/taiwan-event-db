"""ETL 第 1 步（Extract）：下載文化部「全國藝文活動資訊系統」開放資料。

用法（在專案根目錄）：
    .venv\\Scripts\\python etl\\fetch_moc.py

下載的原始 JSON 存在 data/raw/，不做任何修改，方便之後重跑清理、追查資料問題。
資料來源：文化部 文化資料開放服務網 https://opendata.culture.tw/ （政府資料開放授權條款－第1版）
"""
import datetime as dt
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
API = "https://cloud.culture.tw/frontsite/trans/SearchShowAction.do?method=doFindTypeJ&category={code}"

# 文化部的活動類別代碼 → 名稱（只抓和本系統相關的類別）
MOC_CATEGORIES = {
    "1": "音樂",
    "2": "戲劇",
    "3": "舞蹈",
    "6": "展覽",
    "7": "講座",
    "17": "演唱會",
    "19": "研習課程",
}


def fetch(code: str, retries: int = 3) -> list:
    url = API.format(code=code)
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8-sig"))
        except Exception as exc:  # 文化部的伺服器偶爾逾時，等一下再試
            if attempt == retries:
                raise
            print(f"  類別 {code} 第 {attempt} 次失敗（{exc}），5 秒後重試")
            time.sleep(5)
    return []


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for code, name in MOC_CATEGORIES.items():
        data = fetch(code)
        (RAW_DIR / f"moc_{code}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        print(f"類別 {code} {name}：{len(data)} 筆")
    (RAW_DIR / "fetched_at.txt").write_text(dt.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")


if __name__ == "__main__":
    main()
