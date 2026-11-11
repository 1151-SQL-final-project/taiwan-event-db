"""偵測可能重複上架的活動（管理員審核時提醒）。

候選活動由 sql/admin/similar_events.sql 撈出（日期重疊、已上架或待審核），這裡再比對：
- 名稱相似度：去掉空白、標點、括號後，比較「相鄰兩個字」有多少相同（Dice 係數，0～1）；
  一個名稱完整包含另一個（例如多了年份、場次）也算很相似
- 同一個場館、同一個縣市、活動網址相同

規則（demo/mock-api.js 的線上示範版用同一套規則，改這裡要一起改）：
- 名稱相似度 ≥ 80% 而且同一個場館 → 「很可能重複」
- 名稱相似度 ≥ 60% 而且同一個場館（例如同系列不同場次）、≥ 70% 而且同縣市、
  或 ≥ 90%（不同縣市，例如巡演） → 「可能重複」
"""
import re
import unicodedata
from collections import Counter

LIKELY, POSSIBLE = "很可能重複", "可能重複"
# (等級, 名稱相似度門檻, 地點條件)，由上往下比對，符合第一條就停
RULES = [
    (LIKELY, 0.8, "venue"),
    (POSSIBLE, 0.6, "venue"),
    (POSSIBLE, 0.7, "city"),
    (POSSIBLE, 0.9, "any"),
]


def normalize(title: str) -> str:
    """全形轉半形、英文轉小寫，只留下文字與數字（去掉空白、標點、各種括號）。"""
    text = unicodedata.normalize("NFKC", title or "").lower()
    return re.sub(r"[\W_]+", "", text)


def title_similarity(a: str, b: str) -> float:
    a, b = normalize(a), normalize(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if min(len(a), len(b)) >= 4 and (a in b or b in a):
        return 0.9
    pairs_a = Counter(a[i:i + 2] for i in range(len(a) - 1)) or Counter([a])
    pairs_b = Counter(b[i:i + 2] for i in range(len(b) - 1)) or Counter([b])
    common = sum((pairs_a & pairs_b).values())
    return 2 * common / (sum(pairs_a.values()) + sum(pairs_b.values()))


def compare(event: dict, other: dict) -> dict | None:
    """event 是待審核的活動，other 是候選活動；不像重複時回傳 None。"""
    score = title_similarity(event["EventTitle"], other["EventTitle"])
    same_venue = event["EventVenue_FK"] == other["EventVenue_FK"]
    same_city = event["CityName"] == other["CityName"]
    place_ok = {"venue": same_venue, "city": same_city, "any": True}
    level = next((lv for lv, threshold, place in RULES if score >= threshold and place_ok[place]), None)
    if level is None:
        return None
    reasons = [f"名稱相似度 {round(score * 100)}%",
               "同一個場館" if same_venue else ("同縣市" if same_city else f"不同縣市（{other['CityName']}）"),
               "日期重疊"]
    if event.get("EventURL") and event["EventURL"] == other.get("EventURL"):
        reasons.append("活動網址相同")
    return {"EventID": other["EventID"], "EventTitle": other["EventTitle"], "EventStatus": other["EventStatus"],
            "EventStartDate": other["EventStartDate"], "EventEndDate": other["EventEndDate"],
            "VenueName": other["VenueName"], "CityName": other["CityName"], "OrganizerName": other["OrganizerName"],
            "EventOrganizer_FK": other["EventOrganizer_FK"],
            "Level": level, "Score": round(score, 2), "Reasons": reasons}


def find_similar(event: dict, candidates: list[dict]) -> list[dict]:
    """回傳可能重複的活動，最像的排前面（很可能重複優先）。"""
    found = [m for c in candidates if (m := compare(event, c))]
    found.sort(key=lambda m: (m["Level"] != LIKELY, -m["Score"], m["EventID"]))
    return found
