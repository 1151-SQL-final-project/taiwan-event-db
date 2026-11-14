"""ETL 第 2 步（Transform）：把文化部原始 JSON 清理成本系統的 CSV 格式。

用法（在專案根目錄，先跑過 fetch_moc.py）：
    .venv\\Scripts\\python etl\\clean_moc.py

輸入：data/raw/moc_*.json
輸出：
    data/clean/moc_venues.csv     場館（同名同縣市合併成一筆）
    data/clean/moc_events.csv     活動（一個場館一列：同一場活動在多個場館舉辦時拆成多列，EventKey 相同；
                                  同一場活動被登錄兩次的會合併，見 merge_twins）
    data/clean/moc_discounts.csv  從優惠說明自動擷取的優惠（標記「待確認」）
    data/review/moc_rejects.csv               無法判斷縣市而捨棄的場次，附原因
    data/review/moc_discount_candidates.csv   提到優惠、但無法自動擷取的活動，給人工建檔參考
    data/review/etl_report.md                 每條清理規則處理了幾筆（期末報告可用）

清理規則見每個函式的說明；規則改了就重跑，原始資料不會被動到。
"""
import collections
import csv
import datetime as dt
import html
import json
import pathlib
import re
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
CLEAN_DIR = ROOT / "data" / "clean"
REVIEW_DIR = ROOT / "data" / "review"

SOURCE_NAME = "文化部全國藝文活動資訊系統"

CITIES = ["臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "宜蘭縣", "苗栗縣", "臺中市", "彰化縣",
          "南投縣", "雲林縣", "嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣", "花蓮縣", "臺東縣",
          "澎湖縣", "金門縣", "連江縣"]

# 地址沒寫縣市時，用行政區判斷。同名行政區（例如中正區：臺北、基隆都有）依清單順序取第一個，並記錄在報告裡
DISTRICTS = {
    "臺北市": "中正 大同 中山 松山 大安 萬華 信義 士林 北投 內湖 南港 文山",
    "臺中市": "中 東 南 西 北 西屯 南屯 北屯 豐原 東勢 大甲 清水 沙鹿 梧棲 后里 神岡 潭子 大雅 新社 石岡 外埔 大安 "
             "烏日 大肚 龍井 霧峰 太平 大里 和平",
    "高雄市": "新興 前金 苓雅 鹽埕 鼓山 旗津 前鎮 三民 楠梓 小港 左營 仁武 大社 岡山 路竹 阿蓮 田寮 燕巢 橋頭 梓官 "
             "彌陀 永安 湖內 鳳山 大寮 林園 鳥松 大樹 旗山 美濃 六龜 內門 杉林 甲仙 桃源 那瑪夏 茂林 茄萣",
    "新北市": "板橋 三重 中和 永和 新莊 新店 樹林 鶯歌 三峽 淡水 汐止 瑞芳 土城 蘆洲 五股 泰山 林口 深坑 石碇 坪林 "
             "三芝 石門 八里 平溪 雙溪 貢寮 金山 萬里 烏來",
    "桃園市": "桃園 中壢 大溪 楊梅 蘆竹 大園 龜山 八德 龍潭 平鎮 新屋 觀音 復興",
    "臺南市": "東 南 北 安南 安平 中西 新營 鹽水 白河 柳營 後壁 東山 麻豆 下營 六甲 官田 大內 佳里 學甲 西港 七股 "
             "將軍 北門 新化 善化 新市 安定 山上 玉井 楠西 南化 左鎮 仁德 歸仁 關廟 龍崎 永康",
    "基隆市": "仁愛 信義 中正 中山 安樂 暖暖 七堵",
    "新竹市": "東 北 香山",
    "嘉義市": "東 西",
}
TOWNSHIPS = {  # 縣轄市、鄉鎮（常見的）
    "宜蘭市": "宜蘭縣", "羅東鎮": "宜蘭縣", "五結鄉": "宜蘭縣", "礁溪鄉": "宜蘭縣", "頭城鎮": "宜蘭縣",
    "竹北市": "新竹縣", "竹東鎮": "新竹縣", "苗栗市": "苗栗縣", "頭份市": "苗栗縣",
    "彰化市": "彰化縣", "員林市": "彰化縣", "鹿港鎮": "彰化縣", "和美鎮": "彰化縣",
    "南投市": "南投縣", "埔里鎮": "南投縣", "草屯鎮": "南投縣", "斗六市": "雲林縣", "虎尾鎮": "雲林縣",
    "太保市": "嘉義縣", "朴子市": "嘉義縣", "民雄鄉": "嘉義縣", "屏東市": "屏東縣", "潮州鎮": "屏東縣",
    "花蓮市": "花蓮縣", "吉安鄉": "花蓮縣", "臺東市": "臺東縣", "池上鄉": "臺東縣", "關山鎮": "臺東縣",
    "馬公市": "澎湖縣", "金城鎮": "金門縣", "金湖鎮": "金門縣", "南竿鄉": "連江縣",
}
DISTRICT_TO_CITIES: dict[str, list[str]] = collections.defaultdict(list)
for _city, _names in DISTRICTS.items():
    for _d in _names.split():
        DISTRICT_TO_CITIES[_d + "區"].append(_city)
for _t, _city in TOWNSHIPS.items():
    DISTRICT_TO_CITIES[_t].append(_city)

# 文化部類別 → 本系統類別；之後再依標題關鍵字細分
CATEGORY_MAP = {"1": "音樂表演", "17": "音樂表演", "2": "戲劇", "3": "舞蹈", "6": "展覽", "7": "講座", "19": "研習營隊"}
WORKSHOP_WORDS = ["工作坊", "DIY", "手作", "體驗課"]
SCIENCE_WORDS = ["科學", "科普", "天文", "恐龍", "化石", "生物", "自然史", "昆蟲", "宇宙", "太空"]
CAMP_WORDS = ["營隊", "研習營", "夏令營", "冬令營", "寒假營", "暑假營"]

# 優惠類型 → 在優惠說明裡找的關鍵字
DISCOUNT_KEYWORDS = {
    "學生優惠": ["學生"],
    "早鳥優惠": ["早鳥"],
    "敬老優惠": ["敬老", "65歲", "六十五歲", "長者"],
    "團體優惠": ["團體"],
}

stats = collections.Counter()
district_guesses = collections.Counter()


# ---------- 文字清理 ----------

def clean_text(text: str | None) -> str:
    """去掉 HTML 標籤與跳脫字元、統一換行、去掉頭尾空白。"""
    if not text:
        return ""
    text = html.unescape(re.sub(r"<br\s*/?>", "\n", text, flags=re.I))
    text = re.sub(r"<[^>]+>", "", text).replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def fit(text: str, limit: int) -> str:
    """截到 Access 欄位放得下的長度。Access 以 UTF-16 計算長度，emoji 這類字元佔 2 格，所以不能直接用 [:limit]。"""
    while len(text.encode("utf-16-le")) // 2 > limit:
        text = text[:-1]
    return text


def one_line(text: str | None) -> str:
    return re.sub(r"\s+", " ", clean_text(text)).strip()


def normalize_city_names(text: str) -> str:
    """「台北市」→「臺北市」：只改縣市名稱，路名裡的「台」不動。"""
    fixed = re.sub(r"台(北市|中市|南市|東縣)", r"臺\1", text)
    if fixed != text:
        stats["地址：台→臺"] += 1
    return fixed


def normalize_address(address: str) -> str:
    """全形英數字轉半形、去掉多餘空白、去掉郵遞區號。"""
    address = unicodedata.normalize("NFKC", address)
    address = re.sub(r"\s+", "", address)
    address = re.sub(r"^\d{3,6}", "", address)  # 郵遞區號
    return normalize_city_names(address)


# ---------- 縣市判斷 ----------

# (標準化地址, 縣市)：所有原始資料中「有寫縣市」的地址，main() 一開始填入
KNOWN_ADDRESSES: list[tuple[str, str]] = []


def address_key(address: str) -> str:
    """比對地址用：去掉縣市、樓層與括號說明，「21之1號」與「21-1號」視為相同。"""
    key = re.sub(r"[（(].*?[）)]", "", address)
    key = re.sub(r"(B?\d+|[一二三四五六七八九十]+)[樓F].*$", "", key, flags=re.I)
    return key.replace("之", "-").replace("－", "-")

def find_city(address: str, venue_name: str) -> tuple[str | None, str, str]:
    """回傳（縣市, 清理後地址, 判斷方式）。找不到縣市時縣市為 None。"""
    # 1. 地址裡有縣市名稱：從縣市名稱開始截取（去掉「無無臺東縣…」這類前綴）
    positions = [(address.find(c), c) for c in CITIES if c in address]
    if positions:
        pos, city = min(positions)
        cleaned = address[pos:].rstrip(")）")
        return city, cleaned, "地址有縣市" if pos == 0 else "地址有縣市（去除前綴）"
    # 2. 場館名稱裡有縣市名稱，例如「嘉義市美術館」
    name = normalize_city_names(unicodedata.normalize("NFKC", venue_name))
    for city in CITIES:
        if city in name:
            return city, city + address, "場館名稱有縣市"
    # 3. 同一個地址在別筆資料有寫縣市，例如別的活動寫「臺北市中正區中山南路21-1號」
    key = address_key(address)
    matches = {city for full, city in KNOWN_ADDRESSES if len(key) >= 6 and full.endswith(key)}
    if len(matches) == 1:
        city = matches.pop()
        return city, city + address, "其他資料有同地址"
    # 4. 地址開頭是行政區或鄉鎮，例如「西屯區惠來路…」
    match = re.match(r"^(.{1,3}?[區鄉鎮市])", address)
    if match and match.group(1) in DISTRICT_TO_CITIES:
        candidates = DISTRICT_TO_CITIES[match.group(1)]
        if len(candidates) > 1:
            district_guesses[f"{match.group(1)} → {candidates[0]}（也可能是 {'、'.join(candidates[1:])}）"] += 1
        return candidates[0], candidates[0] + address, "依行政區推定"
    return None, address, "無法判斷縣市"


# ---------- 場館 ----------

PLACEHOLDER_VENUE = re.compile(r"^(.{1,4}[區鄉鎮市])[（(](.{2,3}[市縣])[）)]=?$")


def clean_venue_name(name: str, address: str) -> str:
    """「桃園區（桃園市）=」這種只有行政區的名稱，改用地址當場館名稱。"""
    name = re.sub(r"\s+", " ", unicodedata.normalize("NFKC", name)).strip().rstrip("=").strip()
    if not name or PLACEHOLDER_VENUE.match(name):
        stats["場館名稱：只有行政區，改用地址"] += 1
        return fit(address, 50)
    return fit(name, 50)


# ---------- 票價 ----------

# 票種名稱有這些字，代表是優惠票，不能拿來當「原價」
DISCOUNT_TIER_WORDS = ["學生", "敬老", "長者", "團體", "優待", "優惠", "半票", "兒童", "孩童", "身障", "身心",
                       "早鳥", "軍警", "里民", "縣民", "市民", "愛心", "會員", "之友", "折", "65歲"]
# 斜線兩邊都是數字時是日期（10/04），不切
PIECE_SPLIT = re.compile(r"[;；、,，\n]|(?<!\d)/|/(?!\d)")


def parse_price_tiers(text: str) -> list[tuple[str, int]]:
    """把票價說明拆成（票種名稱, 價格）。支援：
    「全票+300;優待票+150」「3000、2700、2200」「300」「1000↑」「全票100元，半票70元」「〔原價票〕$900」
    """
    tiers = []
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?:^|(?<=\s))\d{1,2}[、.]\s*(?=\D)", "\n", text)  # 條列編號「1、設籍本縣」不是價格
    for piece in PIECE_SPLIT.split(text):
        piece = piece.strip()
        if not piece:
            continue
        match = (re.search(r"^(.*)\+\s*(\d[\d,]*)\s*元?\s*$", piece)                       # 全票+300
                 or re.fullmatch(r"()(?:NT\$|\$)?\s*(\d[\d,]*)\s*(?:元|起|↑)?", piece)     # 300、1000↑
                 or re.search(r"^(.*?)(?:NT\$|\$)\s*(\d[\d,]*)", piece)                   # 〔原價票〕$900
                 or re.search(r"^(.*?)(\d[\d,]*)\s*元", piece))                           # 全票100元
        if match:
            tiers.append((match.group(1), int(match.group(2).replace(",", ""))))
    return tiers


FREE_EVENTS: list[dict] = []  # 判斷為免費的活動與依據，寫到 data/review/moc_free_events.csv 給人工抽查


def load_link_fixes() -> dict[str, str]:
    """data/manual/link_fixes.csv：人工確認過失效的連結（舊網址 → 新網址；新網址空白 = 清空）。
    開放資料每次更新都會蓋掉資料庫，所以修正記在這裡，重跑 ETL 也不會消失。"""
    path = ROOT / "data" / "manual" / "link_fixes.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        return {r["OldURL"].strip(): r["NewURL"].strip() for r in csv.DictReader(f)}


LINK_FIXES = load_link_fixes()


def fix_url(url: str) -> str:
    """有些活動把兩個網址接在一起（https://a；https://b），取第一個；再套用人工修正清單。"""
    first = re.split(r"[；，\s]+|[;,](?=https?://)", url.strip())[0]
    if first != url:
        stats["連結：多個網址接在一起，取第一個"] += 1
    if first in LINK_FIXES:
        stats["連結：套用人工修正清單"] += 1
        return LINK_FIXES[first]
    return first


def image_url(raw: dict) -> str:
    """文化部的 imageUrl 開頭常重複網域（https://cloud.culture.twhttps://cloud.culture.tw/...），取最後一段。"""
    url = raw.get("imageUrl") or ""
    url = url[url.rfind("https://"):] if "https://" in url else ""
    return url if len(url) <= 255 else ""


def show_times(shows: list[dict]) -> str:
    """場次時間（只用來顯示）：開始|結束;開始|結束，時間排序、去掉重複。"""
    iso = lambda text: text[:16].replace("/", "-").replace(" ", "T")  # noqa: E731
    return ";".join(sorted({f"{iso(s['time'])}|{iso(s.get('endTime') or s['time'])}" for s in shows}))


def is_discount_tier(label: str) -> bool:
    return any(w in label for w in DISCOUNT_TIER_WORDS)


# 免費判斷寧可漏標，也不要標錯（標錯會讓人白跑一趟）：
# 要有「整場活動免費」的明確說法，而且同一句不是特定對象的免票，全文也沒有寫售價
_FREE_SAYS = re.compile(r"免費(?:入場|參觀|參加|報名|演出|展出|觀賞|講座|線上觀展)|活動免費"
                        r"|(?:費用|票價|門票|入場)\s*[｜|：:]\s*免費|自由(?:入場|參觀|參加)|[無不]需購票")
_FREE_ONLY_SOME = re.compile(r"以下|未滿|兒童|孩童|長者|六十五|65|設籍|市民|縣民|原住民|身心障礙|持有|憑|借書|滿\d|會員|對象|資格|公告")
_HAS_PRICE = re.compile(r"全票|半票|優待票|\d+\s*元")


def free_evidence(raw: dict, price_texts: list[str]) -> str:
    """整場活動免費時，回傳判斷依據的那一段文字；否則回傳空字串。"""
    text = "\n".join([raw["title"], clean_text(raw.get("discountInfo")), clean_text(raw.get("comment")),
                      clean_text(raw.get("descriptionFilterHtml")), *price_texts])
    if _HAS_PRICE.search(text):
        return ""
    if "免費" in raw["title"]:
        return raw["title"]
    for sentence in re.split(r"[。！？!?\n；;]", text):
        if not _FREE_ONLY_SOME.search(sentence) and (m := _FREE_SAYS.search(sentence)):
            return sentence.strip()[:100] or m.group()
    return ""


def event_price(raw: dict) -> tuple[int | None, str]:
    """回傳（原價, 票價原始說明）。票價規則：一般票種的最低價；0 = 免費；None = 不明。"""
    texts = list(dict.fromkeys(s["price"].strip() for s in raw["showInfo"] if s.get("price", "").strip()))
    note = "；".join(texts)
    if evidence := free_evidence(raw, texts):
        stats["票價：免費"] += 1
        FREE_EVENTS.append({"EventKey": raw["UID"], "EventTitle": one_line(raw["title"]), "Evidence": one_line(evidence)})
        return 0, fit(note or "免費", 100)
    tiers = [t for text in texts for t in parse_price_tiers(text)]
    regular = [price for label, price in tiers if not is_discount_tier(label)]
    if regular:
        stats["票價：解析出數字"] += 1
        if len(regular) < len(tiers):
            stats["票價：排除優惠票種後取最低價"] += 1
        return min(regular), fit(note, 100)
    if tiers:
        stats["票價：只有優惠票種，取最低價"] += 1
        return min(price for _label, price in tiers), fit(note, 100)
    stats["票價：不明（空值）" if not texts else "票價：有文字但無法解析（空值）"] += 1
    return None, fit(note, 100)


# ---------- 類別 ----------

def event_category(raw: dict) -> str:
    category = CATEGORY_MAP[raw["category"]]
    title = raw["title"]
    if any(w in title for w in WORKSHOP_WORDS):
        new = "工作坊"
    elif category == "展覽" and any(w in title for w in SCIENCE_WORDS):
        new = "科普展覽"
    elif any(w in title for w in CAMP_WORDS):
        new = "研習營隊"
    else:
        return category
    if new != category:
        stats[f"類別：{category}→{new}（依標題關鍵字）"] += 1
    return new


# ---------- 優惠 ----------

def extract_discounts(raw: dict, base_price: int | None) -> tuple[list[dict], list[str]]:
    """從優惠說明擷取優惠。回傳（擷取到的優惠, 提到但無法擷取的類型）。

    規則（逐句判斷，一句只要提到某類優惠的關鍵字）：
    - 句子有「免費」「免票」→ 優惠價 0
    - 句子有「X元」→ 優惠價 X
    - 句子有「X折」且活動有最低票價 → 最低票價 × 折數（四捨五入）
    - 早鳥優惠一定要找到截止日期，找不到就不擷取
    - 優惠價不低於原價的（例如「團體參觀券+320」是整團的價格）不算優惠
    """
    text = clean_text(raw.get("discountInfo")) + "\n" + "\n".join(s.get("price", "") for s in raw["showInfo"])
    found: dict[str, dict] = {}
    mentioned = set()
    text = unicodedata.normalize("NFKC", text)  # 先把全形「／」「，」轉半形再切句
    for sentence in re.split(r"[\n。；;◎｜|，,]|(?<!\d)/|/(?!\d)", text):
        sentence = sentence.strip()
        for kind, words in DISCOUNT_KEYWORDS.items():
            if not any(w in sentence for w in words):
                continue
            mentioned.add(kind)
            price = None
            if "免費" in sentence or "免票" in sentence:
                price = 0
            elif m := re.findall(r"(\d+)\s*元", sentence):
                price = int(m[-1])
            elif (m := re.findall(r"(\d{1,2})\s*折", sentence)) and base_price:
                rate = int(m[-1])
                price = round(base_price * (rate / 10 if rate < 10 else rate / 100))
            elif (m := re.search(r"\+\s*(\d+)\s*$", sentence)):  # 票價欄「學生票+300」
                price = int(m.group(1))
            if price is None:
                continue
            if base_price is not None and price >= base_price:
                stats["優惠：價格不低於原價，捨棄"] += 1
                continue
            end_date = None
            if kind == "早鳥優惠":
                d = re.search(r"(20\d{2})[/.\-年](\d{1,2})[/.\-月](\d{1,2})", sentence)
                if not d:
                    continue
                end_date = f"{d.group(1)}/{int(d.group(2)):02d}/{int(d.group(3)):02d}"
            if kind not in found or price < found[kind]["DiscountPrice"]:
                found[kind] = {"DiscountTypeName": kind, "DiscountDescription": fit(sentence, 100),
                               "DiscountPrice": price, "DiscountStartDate": "", "DiscountEndDate": end_date or ""}
    return list(found.values()), sorted(mentioned - found.keys())


OPENTIX_RE = re.compile(r"opentix\.life/(?:program|event)/(\d+)")
FILL_FIELDS = ["EventOriginalPrice", "EventPriceNote", "EventDescription", "EventImageURL"]


def overlaps(a: dict, b: dict) -> bool:
    return a["EventStartDate"] <= b["EventEndDate"] and b["EventStartDate"] <= a["EventEndDate"]


def merge_twins(events: list[dict], discounts: list[dict], candidates: list[dict]):
    """文化部常把同一場活動登錄兩次（UID 不同），網站上就會重複上架。這兩種情況視為同一場、合併成一組：
    1. 同一個 OPENTIX 節目編號（一筆 /program/編號、一筆 /event/編號），日期重疊。
    2. 名稱只差在標點或空白、起訖日相同、同縣市，場館名稱一個包含另一個（例如「臺灣戲曲中心」與「臺灣戲曲中心小舞台」）。
    保留有 /program/ 網址的那組（場次時間、場館比較完整），否則保留場館名稱較詳細的；
    另一組的票價、票價說明、介紹、圖片補進保留那組的空白欄位；優惠改掛到保留的活動（同類優惠已經有就不重複）。
    日期完全不重疊的（例如同一節目不同檔期）不合併。"""
    rows: dict[str, list] = {}
    for e in events:
        rows.setdefault(e["EventKey"], []).append(e)
    rank = lambda k: ("/program/" in rows[k][0]["EventURL"], len(rows[k][0]["_venue"][0]))
    groups: list[list] = []  # 每組是可能重複的 EventKey
    keys_by_id: dict[str, list] = {}
    for e in events:
        m = OPENTIX_RE.search(e["EventURL"])
        if m and e["EventKey"] not in keys_by_id.setdefault(m.group(1), []):
            keys_by_id[m.group(1)].append(e["EventKey"])
    groups += [keys for keys in keys_by_id.values() if len(keys) > 1]
    by_title: dict[tuple, list] = {}
    for e in events:
        by_title.setdefault((re.sub(r"[\s\W_]+", "", e["EventTitle"]), e["EventStartDate"], e["EventEndDate"]), []).append(e)
    for same in by_title.values():
        for i, a in enumerate(same):
            for b in same[i + 1:]:
                (va, ca), (vb, cb) = a["_venue"], b["_venue"]
                if a["EventKey"] != b["EventKey"] and ca == cb and (va in vb or vb in va):
                    groups.append([a["EventKey"], b["EventKey"]])
    replaced = {}  # 被合併掉的 EventKey → 保留的 EventKey
    for keys in groups:
        keys = [k for k in keys if k not in replaced]
        if len(keys) < 2:
            continue
        keep = max(keys, key=rank)  # 同分時取先出現的
        for other in keys:
            if other == keep or not all(any(overlaps(o, k) for k in rows[keep]) for o in rows[other]):
                continue
            for k in rows[keep]:
                twin = next((o for o in rows[other] if overlaps(o, k)), rows[other][0])
                for field in FILL_FIELDS:
                    if not str(k[field]).strip() and str(twin[field]).strip():
                        k[field] = twin[field]
            replaced[other] = keep
            stats["活動：同一場活動登錄兩次，合併"] += 1
            stats["活動：合併後減少的筆數"] += len(rows[other])
    for k in replaced:  # 保留的那組之後又被合併掉時，改指向最後保留的
        while replaced[k] in replaced:
            replaced[k] = replaced[replaced[k]]
    events = [e for e in events if e["EventKey"] not in replaced]
    has = {(d["EventKey"], d["DiscountTypeName"]) for d in discounts if d["EventKey"] not in replaced}
    merged = []
    for d in discounts:
        if d["EventKey"] in replaced:
            d = {**d, "EventKey": replaced[d["EventKey"]]}
            if (d["EventKey"], d["DiscountTypeName"]) in has:
                continue
            has.add((d["EventKey"], d["DiscountTypeName"]))
        merged.append(d)
    titles = {e["EventKey"]: e["EventTitle"] for e in events}
    for d in merged:
        d["EventTitle"] = titles.get(d["EventKey"], d["EventTitle"])
    kept_candidates = {c["EventKey"] for c in candidates if c["EventKey"] not in replaced}
    candidates = [c for c in candidates if c["EventKey"] not in replaced or replaced[c["EventKey"]] not in kept_candidates]
    for c in candidates:
        c["EventKey"] = replaced.get(c["EventKey"], c["EventKey"])
    return events, merged, candidates


# ---------- 主程式 ----------

def write_csv(path: pathlib.Path, rows: list[dict], columns: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    raw_events = []
    for path in sorted(RAW_DIR.glob("moc_*.json")):
        raw_events += json.loads(path.read_text(encoding="utf-8"))
    stats["原始活動"] = len(raw_events)
    today = dt.date.today().strftime("%Y/%m/%d")
    for raw in raw_events:  # 先收集有寫縣市的地址，給沒寫縣市的地址比對
        for show in raw["showInfo"]:
            address = normalize_address(show.get("location") or "")
            city = next((c for c in CITIES if address.startswith(c)), None)
            if city:
                KNOWN_ADDRESSES.append((address_key(address), city))
    stats["地址：台→臺"] = 0  # 上面那一輪不算

    venues: dict[tuple, dict] = {}       # (去空白名稱, 縣市) → 場館
    events, discounts, rejects, candidates = [], [], [], []
    seen_uid = set()

    for raw in raw_events:
        if raw["UID"] in seen_uid:
            stats["活動：重複（同一 UID）"] += 1
            continue
        seen_uid.add(raw["UID"])
        if raw["endDate"] < today:
            stats["活動：已結束，不匯入"] += 1
            continue

        event_sessions = []  # 各場次的場館與日期；最後依場館合併（EventTable 一筆活動只有一個場館）
        for show in raw["showInfo"]:
            stats["原始場次"] += 1
            address = normalize_address(show.get("location") or "")
            city, address, how = find_city(address, show.get("locationName") or "")
            stats[f"縣市判斷：{how}"] += 1
            if city is None:
                rejects.append({"EventTitle": raw["title"], "VenueName": show.get("locationName"),
                                "Address": show.get("location"), "Reason": "無法判斷縣市（可能是國外或地址不完整）"})
                continue
            name = clean_venue_name(show.get("locationName") or "", address)
            # 同縣市、名稱只差在空白、標點或「台／臺」的，視為同一場館（例如「實驗劇場」與「-實驗劇場」）
            key = (re.sub(r"[\s・．.\-—_（）()「」《》【】]", "", name).replace("台", "臺"), city)
            if key not in venues:
                venues[key] = {"VenueName": name, "CityName": city, "VenueAddress": fit(address, 100)}
            else:
                stats["場館：與既有場館合併"] += 1
            event_sessions.append({"_venue": key, "start": show["time"][:10],
                                   "end": (show.get("endTime") or show["time"])[:10],
                                   "time": show["time"], "endTime": show.get("endTime")})
        if not event_sessions:
            stats["活動：所有場次都無法判斷縣市，不匯入"] += 1
            continue
        by_venue: dict[tuple, list] = {}
        for s in event_sessions:
            by_venue.setdefault(s["_venue"], []).append(s)
        stats["原始場次（可判斷縣市）"] += len(event_sessions)
        if len(by_venue) > 1:
            stats["活動：在多個場館舉辦，依場館拆成多筆"] += 1
            stats["活動：拆分後增加的筆數"] += len(by_venue) - 1

        price, note = event_price(raw)
        description = clean_text(raw.get("descriptionFilterHtml"))
        discount_info = clean_text(raw.get("discountInfo"))
        if discount_info and discount_info not in ("--", "無"):
            description += f"\n\n【優惠資訊】\n{discount_info}"
        url = next((u for u in (raw.get("sourceWebPromote"), raw.get("webSales")) if u and u.startswith("http")), "")
        url = fix_url(url)
        title = fit(one_line(raw["title"]), 100)
        category = event_category(raw)
        # 同一個 EventKey 可能有多列（每個場館一列）；只有一個場館時，期間用活動本身的起訖日
        for venue_key, shows in by_venue.items():
            single = len(by_venue) == 1
            events.append({
                "EventKey": raw["UID"], "EventTitle": title, "CategoryName": category, "_venue": venue_key,
                "EventStartDate": raw["startDate"] if single else min(s["start"] for s in shows),
                "EventEndDate": raw["endDate"] if single else max(s["end"] for s in shows),
                "EventOriginalPrice": "" if price is None else price, "EventPriceNote": note,
                "EventURL": url, "EventDataSource": SOURCE_NAME, "EventDescription": description,
                "EventImageURL": image_url(raw), "EventShowTimes": show_times(shows),
            })

        found, unparsed = extract_discounts(raw, price)
        for d in found:
            discounts.append({"EventKey": raw["UID"], "EventTitle": title, **d,
                              "SourceURL": url, "RecordedBy": "ETL自動擷取（待確認）",
                              "RecordedDate": dt.date.today().strftime("%Y/%m/%d")})
            stats[f"優惠：自動擷取 {d['DiscountTypeName']}"] += 1
        if unparsed:
            candidates.append({"EventKey": raw["UID"], "EventTitle": title, "MentionedTypes": "、".join(unparsed),
                               "DiscountInfo": one_line(raw.get("discountInfo"))[:300], "EventURL": url})

    events, discounts, candidates = merge_twins(events, discounts, candidates)
    used = {e["_venue"] for e in events}  # 只有被合併掉的活動用到的場館不匯入
    stats["場館：只有被合併掉的活動用到，不匯入"] = len(venues) - len(used & venues.keys())
    venues = {k: v for k, v in venues.items() if k in used}

    # 不同縣市有同名場館時（例如「演藝廳」），名稱後面加上縣市，讓場館名稱不重複
    name_count = collections.Counter(v["VenueName"] for v in venues.values())
    for v in venues.values():
        if name_count[v["VenueName"]] > 1:
            v["VenueName"] = f"{fit(v['VenueName'], 44)}（{v['CityName']}）"
            stats["場館：不同縣市同名，名稱加註縣市"] += 1
    for e in events:
        e["VenueName"] = venues[e.pop("_venue")]["VenueName"]

    stats["匯入活動（依場館拆分後）"], stats["匯入場館"] = len(events), len(venues)
    stats["匯入活動（不重複 EventKey）"] = len({e["EventKey"] for e in events})

    write_csv(CLEAN_DIR / "moc_venues.csv", list(venues.values()), ["VenueName", "CityName", "VenueAddress"])
    # EventPriceNote 不是資料表欄位：build_db.py 會把它加在 EventDescription 開頭（【票價】…）
    write_csv(CLEAN_DIR / "moc_events.csv", events,
              ["EventKey", "EventTitle", "CategoryName", "VenueName", "EventStartDate", "EventEndDate",
               "EventOriginalPrice", "EventPriceNote", "EventURL", "EventDataSource", "EventDescription",
               "EventImageURL", "EventShowTimes"])
    write_csv(REVIEW_DIR / "moc_free_events.csv", FREE_EVENTS, ["EventKey", "EventTitle", "Evidence"])
    (CLEAN_DIR / "moc_sessions.csv").unlink(missing_ok=True)  # 舊版（9 張表）的場次檔
    write_csv(CLEAN_DIR / "moc_discounts.csv", discounts,
              ["EventKey", "EventTitle", "DiscountTypeName", "DiscountDescription", "DiscountPrice",
               "DiscountStartDate", "DiscountEndDate", "SourceURL", "RecordedBy", "RecordedDate"])
    write_csv(REVIEW_DIR / "moc_rejects.csv", rejects, ["EventTitle", "VenueName", "Address", "Reason"])
    write_csv(REVIEW_DIR / "moc_discount_candidates.csv", candidates,
              ["EventKey", "EventTitle", "MentionedTypes", "DiscountInfo", "EventURL"])
    write_report()


def write_report():
    fetched = (RAW_DIR / "fetched_at.txt").read_text(encoding="utf-8") if (RAW_DIR / "fetched_at.txt").exists() else "?"
    lines = ["# ETL 清理報告", "", f"- 資料下載時間：{fetched}",
             f"- 清理時間：{dt.datetime.now().isoformat(timespec='seconds')}", "", "| 項目 | 筆數 |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(stats.items())]
    if district_guesses:
        lines += ["", "## 依行政區推定縣市（同名行政區，取第一個）", "", "| 推定 | 筆數 |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in district_guesses.most_common()]
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (REVIEW_DIR / "etl_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
