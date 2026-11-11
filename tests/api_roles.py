"""後端 API 測試：三種角色的權限，以及商家上架 → 管理員審核（含退回理由）→ 使用者收藏 → 下架的完整流程，
還有開賣時間（即將開賣、活動狀態篩選、開賣提醒）。

用法（在專案根目錄，執行時會自動建立測試用資料庫）：
    .venv\\Scripts\\python tests\\api_roles.py

- 會另外建一個含（測試）活動的資料庫給測試用（tests/test_db.py），上架、審核、收藏不會弄髒正式資料。
- 全部通過時最後印出「全部通過」，任何一項失敗會以錯誤碼結束。
"""
import datetime as dt
import csv
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import test_db

ROOT = pathlib.Path(__file__).resolve().parent.parent
PORT = 8769
BASE = f"http://127.0.0.1:{PORT}"
results: list[bool] = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(("  ✓ " if ok else "  ✗ ") + name + (f"（{detail}）" if detail else ""), flush=True)


def api(method, path, body=None, token=None):
    """回傳 (HTTP 狀態碼, JSON)。錯誤狀態也回傳，不丟例外。"""
    req = urllib.request.Request(BASE + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json",
                                          **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


# 2×2 的 PNG，測試上傳圖片用
TINY_PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
                         "0000001649444154789c63dc90e0c0c0c0c0c4c0c0c0c0c00000105a0154221d87"
                         "470000000049454e44ae426082")


def upload(data, content_type, token):
    """上傳圖片：請求內容直接是檔案。回傳 (HTTP 狀態碼, JSON)。"""
    req = urllib.request.Request(BASE + "/api/merchant/images", method="POST", data=data,
                                 headers={"Content-Type": content_type, **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read() or b"null")


def login(email):
    status, data = api("POST", "/api/auth/login", {"email": email, "password": "test1234"})
    assert status == 200, (email, data)
    return data["token"]


def search(**params):
    return api("GET", "/api/events?" + urllib.parse.urlencode({"page_size": 100, **params}, doseq=True))[1]


def start_server(db_copy):
    env = {**os.environ, "EVENT_DB_PATH": str(db_copy), "EVENT_UPLOAD_DIR": str(db_copy.parent / "uploads")}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "api", "--port", str(PORT)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE + "/api/health", timeout=2)
            return proc
        except Exception:
            time.sleep(0.5)
    proc.kill()
    raise RuntimeError("後端沒有啟動")


def run():
    today = dt.date.today()
    day = lambda n: (today + dt.timedelta(days=n)).isoformat()  # noqa: E731

    print("【登入與註冊】")
    admin, merchant, student = (login(f"{who}@example.com") for who in ("admin", "merchant", "student"))
    check("三種角色都能登入", all((admin, merchant, student)))
    status, data = api("GET", "/api/me", token=merchant)
    check("/api/me 回傳角色", data.get("UserRole") == "商家", data.get("UserRole"))
    email = f"shop-{uuid.uuid4().hex[:6]}@example.com"
    status, data = api("POST", "/api/auth/register", {"name": "新商家", "email": email, "password": "password123", "role": "商家"})
    check("可以註冊成商家", status == 201 and data["role"] == "商家")
    other_merchant = data["token"]
    status, _ = api("POST", "/api/auth/register",
                    {"name": "壞人", "email": f"x-{uuid.uuid4().hex[:6]}@example.com", "password": "password123", "role": "管理員"})
    check("不能自己註冊成管理員", status == 400)

    print("【偽造的登入 token】")
    bad = {"Authorization": "Bearer a.b.\xe9"}
    def status_with(path):
        try:
            with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=bad), timeout=60) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code
    any_event = search()["items"][0]["EventID"]
    check("含非 ASCII 字元的 token：公開的活動詳情照常（當成沒登入）", status_with(f"/api/events/{any_event}") == 200)
    check("含非 ASCII 字元的 token：需要登入的 API 回傳 401，不是 500", status_with("/api/me") == 401)

    print("【修改名稱】")
    status, data = api("PUT", "/api/me", {"name": "光影文創有限公司"}, token=merchant)
    check("商家可以修改商家名稱", status == 200 and data["UserName"] == "光影文創有限公司")
    check("名稱不能空白", api("PUT", "/api/me", {"name": "   "}, token=merchant)[0] == 400)
    check("沒登入不能改名稱", api("PUT", "/api/me", {"name": "壞人"})[0] == 401)
    concert = search(keyword="年度巨星巡迴演唱會")["items"][0]["EventID"]
    detail = api("GET", f"/api/events/{concert}")[1]
    check("活動詳情的商家名稱跟著更新", detail["OrganizerName"] == "光影文創有限公司" and detail["OrganizerRole"] == "商家")
    opendata = search(keyword="倫敦巴赫")["items"][0]["EventID"]
    check("開放資料的活動上架者是管理員（網頁不顯示商家）", api("GET", f"/api/events/{opendata}")[1]["OrganizerRole"] == "管理員")
    api("PUT", "/api/me", {"name": "示範商家"}, token=merchant)
    status, data = api("POST", "/api/auth/register", {"name": "沒有縣市的人", "email": f"u-{uuid.uuid4().hex[:6]}@example.com",
                                                      "password": "password123", "role": "使用者"})
    check("註冊不用填預設縣市", status == 201)

    print("【權限】")
    check("使用者不能進商家後台", api("GET", "/api/merchant/events", token=student)[0] == 403)
    check("商家不能進管理員後台", api("GET", "/api/admin/events", token=merchant)[0] == 403)
    check("沒登入不能收藏", api("POST", "/api/saves/1")[0] == 401)
    check("商家不能收藏（收藏只給使用者）", api("GET", "/api/saves", token=merchant)[0] == 403)

    print("【自動下架】")
    status, data = api("GET", "/api/admin/events?keyword=" + urllib.parse.quote("已結束的舊展覽"), token=admin)
    check("伺服器啟動時，已結束的活動自動改成已下架", data["items"] and data["items"][0]["EventStatus"] == "已下架",
          data["items"][0]["EventStatus"] if data["items"] else "找不到")
    check("搜尋不到已結束的活動", search(keyword="已結束的舊展覽")["total"] == 0)

    print("【搜尋】")
    total = search()["total"]
    learn = search(category_group="學習類")
    check("類別分組：學習類", 0 < learn["total"] < total and all(e["CategoryGroup"] == "學習類" for e in learn["items"]),
          f"{learn['total']}／{total} 場")
    east = search(region="東部")
    check("地區：東部（活動 → 場館 → 縣市）", all(e["CityRegion"] == "東部" for e in east["items"]), f"{east['total']} 場")
    check("待審核、已退回的活動搜尋不到",
          search(keyword="待審核的親子科學營")["total"] == 0 and search(keyword="被退回的講座")["total"] == 0)

    print("【活動圖片、場次時間、票價】")
    items = search()["items"]
    check("搜尋結果有圖片網址和官網欄位", all("EventImageURL" in e and "EventURL" in e for e in items))
    with_image = [e for e in items if e["EventImageURL"]]
    check("有活動圖片，而且都是 https、不是 OPENTIX 預設圖",
          with_image and all(e["EventImageURL"].startswith("https://") and "/default/" not in e["EventImageURL"] for e in with_image),
          f"前 100 場有 {len(with_image)} 場")
    details = [api("GET", f"/api/events/{e['EventID']}")[1] for e in items[:30]]
    timed = [d["EventShowTimes"] for d in details if d["EventShowTimes"]]
    check("活動詳情有場次時間（開始|結束）", timed and all("|" in t for t in timed), f"前 30 場有 {len(timed)} 場")
    stone = search(keyword="石的詩意")["items"]
    check("只有特定對象免票的活動不算免費（石的詩意：全票 20 元）", stone and all(e["EventOriginalPrice"] == 20 for e in stone))
    free = search(free_only="true")
    check("只看免費有活動", free["total"] > 0 and all(e["EventOriginalPrice"] == 0 for e in free["items"]), f"{free['total']} 場")

    print("【活動連結】")
    with (ROOT / "data" / "manual" / "link_fixes.csv").open(encoding="utf-8-sig", newline="") as f:
        dead = {r["OldURL"] for r in csv.DictReader(f) if not r["NewURL"]}
    links, page = [], 1
    while True:
        result = search(page=page)
        links += [e["EventURL"] for e in result["items"] if e["EventURL"]]
        if page * 100 >= result["total"]:
            break
        page += 1
    check("人工確認失效的連結不會出現在活動上", dead and not dead & set(links), f"清單 {len(dead)} 個")
    check("活動連結沒有多個網址接在一起", not [u for u in links if "；" in u or "，" in u], f"{len(links)} 個連結")

    print("【開賣時間】")
    now = dt.datetime.now().isoformat()
    status, soon = api("GET", "/api/sales/upcoming?days=14")
    check("即將開賣：14 天內開賣的活動，依開賣時間排序",
          status == 200 and soon and all(now < e["EventSaleStartDate"] for e in soon)
          and [e["EventSaleStartDate"] for e in soon] == sorted(e["EventSaleStartDate"] for e in soon)
          and any(e["EventTitle"] == "（測試）年度巨星巡迴演唱會" and e["DaysLeft"] == 2 for e in soon),
          f"{len(soon)} 場")
    check("即將開賣不含已經開賣的", not any(e["EventTitle"] == "（測試）已開賣的獨立樂團專場" for e in soon))
    today_iso = dt.date.today().isoformat()
    ongoing = search(phase="ongoing")
    check("活動狀態：進行中（已經開始）", ongoing["total"] > 0 and all(e["EventStartDate"][:10] <= today_iso for e in ongoing["items"]),
          f"{ongoing['total']} 場")
    upcoming = search(phase="upcoming", page_size=100)
    check("活動狀態：即將開始／開賣（還沒開始，或還沒開賣）",
          all(e["EventStartDate"][:10] > today_iso or (e["EventSaleStartDate"] or "") > now for e in upcoming["items"])
          and upcoming["total"] + ongoing["total"] >= search()["total"], f"{upcoming['total']} 場")
    check("即將開始／開賣包含還沒開賣的演唱會", search(phase="upcoming", keyword="年度巨星巡迴演唱會")["total"] == 1)
    bird_ids = {d["EventID"] for d in api("GET", "/api/discounts/early-bird?days=14")[1]}
    birds = search(phase="early_bird")
    check("活動狀態：早鳥即將截止（和下方區塊同一批）", {e["EventID"] for e in birds["items"]} == bird_ids, f"{birds['total']} 場")
    first = search(sort="sale")["items"][0]
    check("排序：即將開賣的優先", first["EventSaleStartDate"] == soon[0]["EventSaleStartDate"], first["EventTitle"])
    concert = search(keyword="年度巨星巡迴演唱會")["items"][0]["EventID"]
    detail = api("GET", f"/api/events/{concert}")[1]
    check("活動詳情有開賣時間、還沒開賣", detail["EventSaleStartDate"] and detail["IsOnSale"] is False)
    status, sales = api("GET", "/api/saves/sale-reminders?days=14", token=student)
    check("開賣提醒：收藏的活動即將開賣", status == 200 and any(r["EventID"] == concert for r in sales))
    check("開賣提醒只給使用者", api("GET", "/api/saves/sale-reminders", token=merchant)[0] == 403)

    print("【商家上架】")
    status, venue = api("POST", "/api/venues", {"name": f"測試展演空間{uuid.uuid4().hex[:4]}", "city_id": 1,
                                                "address": "臺北市大安區和平東路一段129號"}, token=merchant)
    check("商家新增場館", status == 201 and venue["venue_id"] > 0)
    print("【商家送出前的重複提醒】")
    huashan = next(v["VenueID"] for v in api("GET", "/api/venues", token=merchant)[1] if v["VenueName"] == "華山1914文化創意產業園區")
    copy_of_listed = {"title": "城市光影攝影展（測試）", "venue_id": huashan, "start_date": day(0), "end_date": day(10)}
    status, found = api("POST", "/api/merchant/events/similar", copy_of_listed, token=merchant)
    titles = [s["EventTitle"] for s in found]
    check("和已上架的活動相似 → 送出前提醒", status == 200 and "（測試）城市光影攝影展" in titles, "、".join(titles))
    check("自己還在待審核的活動也會提醒", "（測試）城市光影 攝影展 2026" in titles)
    found = api("POST", "/api/merchant/events/similar", copy_of_listed, token=other_merchant)[1]
    check("看不到其他商家待審核的活動（只列已上架的）",
          found and all(s["EventStatus"] == "上架中" for s in found), "、".join(s["EventTitle"] for s in found))
    status, found = api("POST", "/api/merchant/events/similar", {**copy_of_listed, "title": "完全不一樣的木工課"}, token=merchant)
    check("名稱不像就不提醒", status == 200 and found == [])
    check("送出前檢查只給商家", api("POST", "/api/merchant/events/similar", copy_of_listed, token=student)[0] == 403)
    query = urllib.parse.urlencode({"venue_id": huashan, "start_date": day(0), "end_date": day(10)})
    status, overlap = api("GET", f"/api/merchant/venue-events?{query}", token=merchant)
    check("上架表單：列出同場館、日期重疊的已上架活動",
          status == 200 and "（測試）城市光影攝影展" in [o["EventTitle"] for o in overlap]
          and "（測試）城市光影 攝影展 2026" not in [o["EventTitle"] for o in overlap], "、".join(o["EventTitle"] for o in overlap))
    query = urllib.parse.urlencode({"venue_id": huashan, "start_date": day(400), "end_date": day(401)})
    check("日期不重疊就不列", api("GET", f"/api/merchant/venue-events?{query}", token=merchant)[1] == [])
    check("同場館活動只給商家", api("GET", f"/api/merchant/venue-events?{query}", token=student)[0] == 403)

    print("【商家成效摘要】")
    status, summary = api("GET", "/api/merchant/summary", token=merchant)
    mine = api("GET", "/api/merchant/events", token=merchant)[1]
    by = {r["EventStatus"]: r for r in summary["by_status"]}
    check("依審核狀態分組的場數和我的活動清單一致",
          status == 200 and all(by[s]["EventCount"] == sum(e["EventStatus"] == s for e in mine) for s in by)
          and sum(r["EventCount"] for r in by.values()) == len(mine))
    check("總收藏數 = 各活動收藏數加總", sum(r["SaveCount"] for r in by.values()) == sum(e["SaveCount"] for e in mine))
    camp = next(e for e in mine if e["EventTitle"] == "（測試）寒假天文研習營")
    check("我的活動清單附上還沒截止的早鳥截止日", camp["EarlyBirdEnd"] is not None
          and all(e["EarlyBirdEnd"] is None for e in mine if e["DiscountCount"] == 0))
    check("成效摘要只給商家", api("GET", "/api/merchant/summary", token=student)[0] == 403)

    print("【活動圖片上傳】")
    status, data = upload(TINY_PNG, "image/png", merchant)
    image_url = data.get("url", "") if status == 201 else ""
    check("商家上傳圖片，存成 uploads/檔名", status == 201 and image_url.startswith("uploads/") and image_url.endswith(".png"), image_url)
    with urllib.request.urlopen(BASE + "/" + image_url, timeout=10) as resp:
        check("上傳的圖片可以用回傳的路徑開啟", resp.status == 200 and resp.read() == TINY_PNG)
    check("不是圖片格式不能上傳", upload(b"hello", "text/plain", merchant)[0] == 400)
    check("內容和格式不符（假裝是 PNG）不能上傳", upload(b"hello world!", "image/png", merchant)[0] == 400)
    check("超過 5 MB 不能上傳", upload(TINY_PNG + bytes(5 * 1024 * 1024), "image/png", merchant)[0] == 400)
    check("只有商家可以上傳圖片", upload(TINY_PNG, "image/png", student)[0] == 403 and upload(TINY_PNG, "image/png", None)[0] == 401)

    title = f"（API 測試）學習工作坊 {uuid.uuid4().hex[:6]}"
    event = {"title": title, "category_id": 3, "venue_id": venue["venue_id"], "start_date": day(10), "end_date": day(12),
             "price": 600, "url": "https://example.com/workshop", "description": "API 測試建立的活動",
             "sale_start": f"{day(3)}T12:00", "image_url": image_url,
             "discounts": [{"discount_type_id": 1, "price": 400, "description": "學生價"},
                           {"discount_type_id": 2, "price": 500, "description": "早鳥價", "end_date": day(5)}]}
    before = len(api("GET", "/api/merchant/events", token=merchant)[1])
    bad = {**event, "discounts": [{"discount_type_id": 2, "price": 500, "description": "早鳥沒寫截止日"}]}
    status, data = api("POST", "/api/merchant/events", bad, token=merchant)
    check("早鳥優惠沒填截止日會被資料表驗證規則擋下", status == 400 and "早鳥" in data["detail"], data.get("detail", "")[:40])
    check("擋下時活動也不會建立（同一個交易）", len(api("GET", "/api/merchant/events", token=merchant)[1]) == before)
    status, data = api("POST", "/api/merchant/events", {**event, "end_date": day(-1), "start_date": day(-3)}, token=merchant)
    check("結束日期已過不能上架", status == 400)
    status, data = api("POST", "/api/merchant/events", {**event, "sale_start": f"{day(20)}T12:00"}, token=merchant)
    check("開賣時間不能晚於活動結束日期", status == 400 and "開賣" in data["detail"])
    status, data = api("POST", "/api/merchant/events", event, token=merchant)
    check("上架活動（含 2 筆優惠）→ 待審核", status == 201 and data["status"] == "待審核")
    event_id = data["event_id"]
    check("審核前搜尋不到", search(keyword=title)["total"] == 0)
    check("審核前一般人看不到詳情", api("GET", f"/api/events/{event_id}")[0] == 404)
    status, detail = api("GET", f"/api/events/{event_id}", token=merchant)
    check("上架的商家可以預覽", status == 200 and len(detail["Discounts"]) == 2)
    same = {"title": title, "venue_id": venue["venue_id"], "start_date": day(10), "end_date": day(12), "event_id": event_id}
    check("修改自己的活動時不會和自己比對", api("POST", "/api/merchant/events/similar", same, token=merchant)[1] == [])
    check("開賣時間存進資料庫", detail["EventSaleStartDate"] == f"{day(3)}T12:00:00", detail["EventSaleStartDate"])
    check("活動圖片存進資料庫", detail["EventImageURL"] == image_url, detail["EventImageURL"])
    status, data = api("POST", "/api/merchant/events", {**event, "image_url": "javascript:alert(1)"}, token=merchant)
    check("圖片網址要是 http(s) 或上傳後的路徑", status == 400 and "圖片" in data["detail"])
    check("審核前不能收藏", api("POST", f"/api/saves/{event_id}", token=student)[0] == 404)

    print("【管理員審核】")
    status, data = api("GET", "/api/admin/events?status=" + urllib.parse.quote("待審核"), token=admin)
    check("待審核清單有這場活動", any(e["EventID"] == event_id for e in data["items"]), f"共 {data['total']} 場待審核")
    pending = {e["EventTitle"]: e for e in data["items"]}
    dup = pending.get("（測試）城市光影 攝影展 2026", {}).get("Similar", [])
    check("重複提醒：名稱相似＋同場館＋日期重疊 → 很可能重複",
          dup and dup[0]["EventTitle"] == "（測試）城市光影攝影展" and dup[0]["Level"] == "很可能重複",
          "、".join(dup[0]["Reasons"]) if dup else "沒有提醒")
    check("重複提醒：不像的活動不會被提醒",
          pending["（測試）待審核的親子科學營"]["Similar"] == [] and pending[title]["Similar"] == [])
    check("重複提醒只給管理員", api("GET", f"/api/admin/events/{event_id}/similar", token=merchant)[0] == 403)
    status, review = api("GET", f"/api/admin/events/{pending['（測試）城市光影 攝影展 2026']['EventID']}/review", token=admin)
    history = {r["EventStatus"]: r["EventCount"] for r in review["organizer_history"]}
    check("審核畫面：活動詳情、重複提醒、上架者紀錄一次拿到", status == 200
          and review["event"]["EventTitle"] == "（測試）城市光影 攝影展 2026" and "Discounts" in review["event"]
          and review["similar"] and review["similar"][0]["EventTitle"] == "（測試）城市光影攝影展"
          and history.get("上架中", 0) >= 1, str(history))
    check("審核畫面只給管理員", api("GET", f"/api/admin/events/{event_id}/review", token=merchant)[0] == 403)
    status, data = api("POST", f"/api/admin/events/{event_id}/status", {"status": "上架中"}, token=admin)
    check("通過審核 → 上架中", status == 200 and data["action"] == "通過審核")
    found = search(keyword=title)
    check("通過後搜尋得到", found["total"] == 1 and found["items"][0]["BestDiscountPrice"] == 400)
    check("通過後一般人看得到詳情", api("GET", f"/api/events/{event_id}")[0] == 200)
    status, copy = api("POST", "/api/merchant/events", {**event, "title": title + "（加場）"}, token=merchant)
    status, similar = api("GET", f"/api/admin/events/{copy['event_id']}/similar", token=admin)
    check("商家再上架一次同一場活動 → 審核時提醒已上架的那一場",
          status == 200 and similar and similar[0]["EventID"] == event_id and similar[0]["EventStatus"] == "上架中",
          similar[0]["Level"] if similar else "沒有提醒")
    api("POST", f"/api/admin/events/{copy['event_id']}/status", {"status": "已退回", "reason": "重複上架"}, token=admin)

    print("【使用者收藏】")
    check("收藏", api("POST", f"/api/saves/{event_id}", token=student)[0] == 201)
    check("重複收藏 → 409（複合唯一索引）", api("POST", f"/api/saves/{event_id}", token=student)[0] == 409)

    print("【商家修改 → 重新審核】")
    status, data = api("PUT", f"/api/merchant/events/{event_id}", {**event, "price": 650, "discounts": event["discounts"][:1]},
                       token=merchant)
    check("修改後回到待審核", status == 200 and data["status"] == "待審核")
    check("修改後暫時搜尋不到", search(keyword=title)["total"] == 0)
    saves = api("GET", "/api/saves", token=student)[1]
    check("收藏清單顯示「待審核」", any(s["EventID"] == event_id and s["EventStatus"] == "待審核" for s in saves))
    status, detail = api("GET", f"/api/events/{event_id}", token=merchant)
    check("優惠整批更新（2 筆 → 1 筆）", len(detail["Discounts"]) == 1 and detail["EventOriginalPrice"] == 650)
    check("修改時圖片照樣保留", detail["EventImageURL"] == image_url)
    status, data = api("GET", "/api/admin/events?keyword=" + urllib.parse.quote("恐龍化石"), token=admin)
    other = data["items"][0]["EventID"]
    check("商家不能修改別人的活動", api("PUT", f"/api/merchant/events/{other}", event, token=merchant)[0] == 404)

    print("【退回、違規下架、重新上架】")
    status, data = api("POST", f"/api/admin/events/{event_id}/status", {"status": "已退回"}, token=admin)
    check("退回一定要有理由", status == 400 and "理由" in data["detail"])
    reason = "票價或優惠資訊有誤；補充：學生價請附證明"
    status, _ = api("POST", f"/api/admin/events/{event_id}/status", {"status": "已退回", "reason": reason}, token=admin)
    check("退回 → 已退回", status == 200)
    mine = {e["EventID"]: e for e in api("GET", "/api/merchant/events", token=merchant)[1]}
    check("商家後台看得到退回理由", mine[event_id]["EventRejectReason"] == reason)
    status, _ = api("POST", f"/api/admin/events/{event_id}/status", {"status": "上架中"}, token=admin)
    check("已退回不能直接上架（要商家修改後重新送審）", status == 400)
    api("PUT", f"/api/merchant/events/{event_id}", event, token=merchant)
    status, detail = api("GET", f"/api/events/{event_id}", token=merchant)
    check("商家修改送審後清掉退回理由", detail["EventStatus"] == "待審核" and detail["EventRejectReason"] is None)
    api("POST", f"/api/admin/events/{event_id}/status", {"status": "上架中", "reason": "不該存進去"}, token=admin)
    status, detail = api("GET", f"/api/events/{event_id}", token=admin)
    check("不是退回時不記理由", detail["EventRejectReason"] is None)
    status, _ = api("POST", f"/api/admin/events/{event_id}/status", {"status": "已下架"}, token=admin)
    check("違規下架 → 已下架", status == 200 and search(keyword=title)["total"] == 0)
    status, _ = api("POST", f"/api/admin/events/{event_id}/status", {"status": "上架中"}, token=admin)
    check("重新上架 → 上架中", status == 200 and search(keyword=title)["total"] == 1)
    status, data = api("GET", "/api/admin/events?keyword=" + urllib.parse.quote("已結束的舊展覽"), token=admin)
    ended = data["items"][0]["EventID"]
    status, data = api("POST", f"/api/admin/events/{ended}/status", {"status": "上架中"}, token=admin)
    check("已結束的活動不能重新上架", status == 400, data.get("detail"))

    print("【各審核狀態場數】")
    status, data = api("GET", "/api/admin/events?page_size=1", token=admin)
    check("活動管理的狀態分頁有各審核狀態場數（GROUP BY），加起來等於全部",
          set(data["counts"]) == {"待審核", "上架中", "已退回", "已下架"} and sum(data["counts"].values()) == data["total"],
          json.dumps(data["counts"], ensure_ascii=False))


def main():
    tmp = pathlib.Path(tempfile.mkdtemp())
    db_copy = test_db.build(tmp / "api.accdb")
    server = start_server(db_copy)
    try:
        run()
    except Exception as exc:
        check("測試流程沒有中斷", False, f"{type(exc).__name__}: {str(exc)[:300]}")
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)
    failed = results.count(False)
    print(f"\n{len(results) - failed}／{len(results)} 項通過" + ("，全部通過" if not failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
