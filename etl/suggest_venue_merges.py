"""找出可能是同一個場館、但名稱寫法不同的資料，輸出建議清單給人工確認（不會自動合併）。

用法（在專案根目錄，先跑過 etl\\clean_moc.py）：
    .venv\\Scripts\\python etl\\suggest_venue_merges.py

輸出 data/review/venue_merge_suggestions.csv。判斷依據：
    同地址＋名稱相似  同縣市、地址相同（忽略樓層），名稱相似度高 → 很可能是同一場館
    同地址            地址相同但名稱差很多 → 可能是同一棟建築裡的不同廳（例如音樂廳與戲劇院），通常不該合併
    名稱相似          地址不同但名稱很像 → 可能是地址寫法不同，也可能是不同分館

不自動合併的原因：同一棟建築的不同演出廳也算不同場館，合併錯了，活動會顯示在錯的地點。
"""
import csv
import difflib
import itertools
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "etl"))
from clean_moc import address_key  # noqa: E402


def name_key(name: str) -> str:
    return re.sub(r"[\s・．.\-—（）()「」《》【】]", "", name)


def main():
    with (ROOT / "data" / "clean" / "moc_venues.csv").open(encoding="utf-8-sig") as f:
        venues = list(csv.DictReader(f))
    rows = []
    by_city = {}
    for v in venues:
        by_city.setdefault(v["CityName"], []).append(v)
    for city, group in by_city.items():
        for a, b in itertools.combinations(group, 2):
            same_address = address_key(a["VenueAddress"]) == address_key(b["VenueAddress"])
            ratio = difflib.SequenceMatcher(None, name_key(a["VenueName"]), name_key(b["VenueName"])).ratio()
            contains = name_key(a["VenueName"]) in name_key(b["VenueName"]) or name_key(b["VenueName"]) in name_key(a["VenueName"])
            if same_address and (ratio >= 0.6 or contains):
                kind = "同地址＋名稱相似"
            elif same_address:
                kind = "同地址"
            elif ratio >= 0.85:
                kind = "名稱相似"
            else:
                continue
            rows.append({"Kind": kind, "City": city, "Similarity": f"{ratio:.2f}",
                         "VenueA": a["VenueName"], "AddressA": a["VenueAddress"],
                         "VenueB": b["VenueName"], "AddressB": b["VenueAddress"], "Merge(Y/N)": ""})
    order = {"同地址＋名稱相似": 0, "名稱相似": 1, "同地址": 2}
    rows.sort(key=lambda r: (order[r["Kind"]], -float(r["Similarity"])))
    out = ROOT / "data" / "review" / "venue_merge_suggestions.csv"
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["Kind"])
        writer.writeheader()
        writer.writerows(rows)
    counts = {k: sum(1 for r in rows if r["Kind"] == k) for k in order}
    print(f"共 {len(rows)} 組：{counts}，輸出到 {out}")


if __name__ == "__main__":
    main()
