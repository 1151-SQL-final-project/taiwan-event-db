"""網頁端對端測試：用真的瀏覽器（電腦上的 Edge）自動操作網頁，檢查每個功能。

用法（在專案根目錄，執行時會自動建立測試用資料庫）：
    .venv\\Scripts\\python -m pip install playwright==1.48.0   # 第一次
    .venv\\Scripts\\python tests\\e2e_web.py

- 會另外建一個含（測試）活動的資料庫給測試用（tests/test_db.py），註冊、收藏不會弄髒正式資料。
- 截圖存在 tests/screenshots/（不上傳 git）。
- 全部通過時最後印出「全部通過」，任何一步失敗會印出原因並以錯誤碼結束。
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import uuid

import test_db
from playwright.sync_api import expect, sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "tests" / "screenshots"
PORT = 8767
BASE = f"http://127.0.0.1:{PORT}"
results: list[tuple[str, bool, str]] = []


def check(name, condition, detail=""):
    results.append((name, bool(condition), detail))
    print(("  ✓ " if condition else "  ✗ ") + name + (f"（{detail}）" if detail else ""), flush=True)


def start_server(db_copy: pathlib.Path):
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


def no_horizontal_scroll(page):
    return page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


# 2×2 的 PNG，測試上傳圖片用
TINY_PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000002000000020802000000fdd49a73"
                         "0000001649444154789c63dc90e0c0c0c0c0c4c0c0c0c0c00000105a0154221d87"
                         "470000000049454e44ae426082")


def waited(expectation) -> bool:
    """等畫面出現預期的結果（Access 查詢有時要一兩秒），逾時回傳 False，不中斷測試。"""
    try:
        expectation()
        return True
    except AssertionError:
        return False


def count_from_heading(page):
    text = page.locator("#result-count").inner_text()
    return int("".join(ch for ch in text if ch.isdigit()) or 0)


def search_state_reset(page):
    """重新載入找活動頁（清掉前一次的搜尋條件）。"""
    page.goto(BASE + "/#/search")
    page.reload()


def run(p):
    browser = p.chromium.launch(channel="msedge")
    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-TW")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    # 「Failed to load resource」是 API 回傳 4xx 時瀏覽器自動印的（測試故意送出錯誤資料），不算程式錯誤
    page.on("console", lambda m: errors.append(m.text)
            if m.type == "error" and not m.text.startswith("Failed to load resource") else None)
    page.on("response", lambda r: errors.append(f"HTTP {r.status} {r.url}") if r.status >= 400 and r.url.startswith(BASE) and "/api/" not in r.url else None)

    print("【首頁】")
    page.goto(BASE + "/#/")
    expect(page.locator(".home-name")).to_have_text("探點", timeout=15000)
    check("首頁顯示 logo", page.locator(".home-art img").evaluate("img => img.complete && img.naturalWidth > 0"))
    check("首頁有 logo、名稱與介紹（沒有搜尋表單）", page.locator("#app form").count() == 0 and page.locator(".lead").is_visible())
    check("首頁有「本週學生優惠」", waited(lambda: expect(page.locator("#home-student .event-card").first).to_be_visible(timeout=15000)),
          f"{page.locator('#home-student .event-card').count()} 場")
    check("首頁有「這週末」", waited(lambda: expect(page.locator("#home-weekend .event-card").first).to_be_visible(timeout=15000)),
          f"{page.locator('#home-weekend .event-card').count()} 場")
    check("首頁每區最多 6 場", page.locator("#home-student .event-card").count() <= 6 and page.locator("#home-weekend .event-card").count() <= 6)
    page.screenshot(path=SHOTS / "00_home.png", full_page=True)
    check("首頁有「登入／註冊」按鈕", page.locator(".home-actions a[href='#/login']").is_visible())
    page.locator(".home-actions a:has-text('找活動')").click()
    page.wait_for_url("**/#/search")
    check("首頁「找活動」按鈕 → 找活動頁", waited(lambda: expect(page.locator("#filters")).to_be_visible(timeout=10000)))

    print("【找活動】")
    page.goto(BASE + "/#/")
    expect(page.locator("#home-student .event-card").first).to_be_visible(timeout=15000)
    student_all = page.locator("#home-student [data-see-all]")
    if student_all.count():
        student_all.click()
        expect(page.locator("#results .event-card").first).to_be_visible(timeout=15000)
        check("首頁「看全部」帶著學生優惠和日期到找活動",
              page.locator("label.chip:has-text('學生優惠') input").is_checked() and page.locator("[name=date_from]").input_value() != "")
    search_state_reset(page)
    expect(page.locator("#results .event-card").first).to_be_visible(timeout=15000)
    check("篩選條件直接顯示，沒有「更多篩選」；今天、這個週末在日期旁，學生優惠在優惠裡",
          page.locator("#filter-more").is_visible() and page.locator("#filter-toggle").count() == 0
          and page.locator(".quick-dates [data-quick=today]").is_visible() and page.locator(".quick-dates [data-quick=weekend]").is_visible()
          and page.locator("label.chip:has-text('學生優惠')").is_visible())
    check("卡片都有圖片或類別插圖", page.locator(".event-card").count() == page.locator(".event-card .event-thumb").count())
    check("活動卡片不再顯示「票價未定」", "票價未定" not in page.locator("#results").inner_text())
    total = count_from_heading(page)
    check("找活動頁載入活動", total > 100, f"{total} 場")
    check("早鳥即將截止區塊顯示", page.locator("#early-bird .strip-item").count() > 0,
          f"{page.locator('#early-bird .strip-item').count()} 筆")
    check("即將開賣區塊顯示", waited(lambda: expect(page.locator("#sale-soon .strip-item").first).to_be_visible(timeout=10000)),
          f"{page.locator('#sale-soon .strip-item').count()} 筆")

    above = "document.querySelector('#highlights').compareDocumentPosition(document.querySelector('#results')) & 4"
    check("剛打開時，即將開賣、早鳥區塊在搜尋結果上面", page.evaluate(above) == 4)
    birds = page.locator("#early-bird .strip-item")
    n_birds = birds.count()
    check("早鳥區塊先顯示前 4 場", page.locator("#early-bird .strip-item:visible").count() == min(4, n_birds), f"共 {n_birds} 場")
    if n_birds > 4:
        more = page.locator("#early-bird .strip-more")
        more.click()
        check("按「顯示更多」顯示全部", page.locator("#early-bird .strip-item:visible").count() == n_birds)
        more.click()
        check("按「收合」回到 4 場", page.locator("#early-bird .strip-item:visible").count() == 4 and "顯示更多" in more.inner_text())

    check("搜尋表單沒有「售票」列，改成活動狀態", page.locator("[name=not_on_sale]").count() == 0
          and page.locator("[name=phase]").count() == 4)
    page.locator("label.chip:has-text('即將開始／開賣')").click()
    page.wait_for_function(f"!document.querySelector('#result-count').textContent.includes('{total:,}')")
    check("搜尋之後，即將開賣、早鳥區塊移到搜尋結果下面",
          page.locator("#highlights-below #highlights").count() == 1 and page.evaluate(above) == 0)
    upcoming = count_from_heading(page)
    check("活動狀態：即將開始／開賣", 0 < upcoming < total, f"{upcoming} 場")
    page.locator("label.chip:has-text('早鳥即將截止')").first.click()
    page.wait_for_function(f"!document.querySelector('#result-count').textContent.includes('{upcoming:,}')")
    bird_titles = set(page.locator("#early-bird .strip-title").all_text_contents())  # 收合的卡片也要算
    card_titles = set(page.locator(".event-card h3").all_inner_texts())
    check("活動狀態：早鳥即將截止（和下方區塊同一批活動）", card_titles and card_titles <= bird_titles, f"{len(card_titles)} 場")
    page.locator("[name=phase][value='']").evaluate("el => el.closest('label').click()")
    page.wait_for_timeout(1500)

    page.locator("label.chip:has-text('東部')").click()
    page.wait_for_function(f"!document.querySelector('#result-count').textContent.includes('{total:,}')")
    east = count_from_heading(page)
    cards = page.locator(".event-card .event-meta").all_inner_texts()
    check("地區篩選：東部", 0 < east < total and all(any(c in t for c in ("宜蘭", "花蓮", "臺東")) for t in cards),
          f"{east} 場，卡片都在宜蘭／花蓮／臺東")
    page.locator("label.chip:has-text('全部')").first.click()
    page.wait_for_timeout(1500)

    check("找活動頁沒有「類型」按鈕列，只有下拉選單", page.locator("[name=category_group]").count() == 0)
    page.locator("[name=category]").select_option(label="全部學習類")
    page.wait_for_timeout(2500)
    learn = count_from_heading(page)
    learning = {"展覽", "講座", "工作坊", "科普展覽", "研習營隊"}
    tags = page.locator(".event-card .tag:first-child").all_inner_texts()
    check("類型篩選：學習類", 0 < learn < total and all(t in learning for t in tags), f"{learn} 場")
    page.locator("[name=category]").select_option("")

    # 故意快速連點（全部 → 學生優惠），確認畫面顯示的是最後一次搜尋的結果
    page.locator("label.chip:has-text('學生優惠')").click()
    page.wait_for_timeout(3000)
    student = count_from_heading(page)
    check("優惠篩選：學生優惠", 0 < student < total, f"{student} 場")
    check("學生優惠的卡片都標「有優惠」或免費",
          all("有優惠" in t or "免費" in t for t in page.locator(".event-card").all_inner_texts()[:10]))
    page.locator("label.chip:has-text('學生優惠')").click()

    page.locator("[data-quick='weekend']").click()
    page.wait_for_timeout(1500)
    check("快速日期：這個週末會填入日期", page.locator("[name=date_from]").input_value() != "")
    page.locator("button[type=reset]").click()
    page.wait_for_timeout(1500)
    check("清除條件後，區塊回到搜尋結果上面", page.locator("#highlights-below #highlights").count() == 0)

    page.locator("#sort").select_option("price")
    page.wait_for_timeout(1500)
    prices = page.locator(".event-card .price").all_inner_texts()[:8]
    nums = [int("".join(c for c in t if c.isdigit())) for t in prices if "NT$" in t]
    check("排序：價格低到高", nums == sorted(nums), " → ".join(prices[:5]))
    page.locator("#sort").select_option("date")
    page.wait_for_timeout(1000)

    if page.locator("#more").is_visible():
        before = page.locator(".event-card").count()
        page.locator("#more").click()
        page.wait_for_timeout(1500)
        check("載入更多", page.locator(".event-card").count() > before, f"{before} → {page.locator('.event-card').count()}")
    page.screenshot(path=SHOTS / "01_search.png")

    print("【活動詳情】")
    page.locator("#early-bird .strip-item").first.click()
    expect(page.locator(".detail-head h1")).to_be_visible()
    check("詳情頁有場館與地址", page.locator(".session-time").count() == 1)
    map_link = page.locator("a:has-text('Google 地圖')").first.get_attribute("href") or ""
    venue = page.locator(".session-time").first.inner_text()
    check("Google 地圖連結用場館名稱查", map_link.startswith("https://www.google.com/maps/search/?api=1&query=")
          and urllib.parse.unquote(map_link.split("query=")[1]) in venue, urllib.parse.unquote(map_link.split("query=")[1]))
    check("詳情頁顯示早鳥優惠與截止日", page.locator(".discount:has-text('早鳥')").count() > 0
          and "截止" in page.locator(".side").inner_text())
    page.screenshot(path=SHOTS / "02_detail.png")
    event_url = page.url

    page.locator("#save-btn").click()
    page.wait_for_url("**/#/login")
    check("未登入按收藏 → 導到登入頁", page.url.endswith("#/login"))

    print("【註冊與收藏】")
    page.locator("[data-tab=register]").click()
    email = f"e2e-{uuid.uuid4().hex[:8]}@example.com"
    form = page.locator("#register-form")
    check("註冊表單不提管理員帳號", "管理員" not in form.inner_text())
    form.locator("label.chip:has-text('商家')").click()
    check("註冊時選商家，名稱欄位變成「商家名稱」", page.locator("#name-label").inner_text() == "商家名稱")
    form.locator("label.chip:has-text('使用者')").click()
    check("選使用者時是「暱稱」", page.locator("#name-label").inner_text() == "暱稱")
    form.locator("[name=name]").fill("測試機器人")
    form.locator("[name=email]").fill(email)
    form.locator("[name=password]").fill("short")
    form.locator("button").click()
    check("密碼太短：瀏覽器擋下", page.url.endswith("#/login"))
    form.locator("[name=password]").fill("password123")
    check("註冊表單沒有預設查詢縣市", form.locator("[name=default_city_id]").count() == 0)
    form.locator("button").click()
    page.wait_for_url(event_url)
    check("註冊後回到原本的活動頁", page.url == event_url)
    check("右上角顯示使用者名稱", page.locator("#nav-account").inner_text() == "測試機器人")

    page.locator("#save-btn").click()
    expect(page.locator("#save-btn")).to_have_text("✓ 已收藏")
    check("收藏成功", True)
    title = page.locator("h1").inner_text()

    page.goto(BASE + "/#/saves")
    expect(page.locator(".save-row").first).to_be_visible()
    check("我的收藏列出剛收藏的活動", page.locator(f".save-row:has-text('{title[:10]}')").count() == 1)
    thumb = page.locator(f".save-row:has-text('{title[:10]}') .save-thumb")
    check("收藏的活動有縮圖（活動圖片或類別插圖），點縮圖到活動頁",
          thumb.locator(".event-thumb").count() == 1 and (thumb.get_attribute("href") or "").startswith("#/event/"))
    check("收藏提醒顯示即將截止的優惠", page.locator(".reminder").count() > 0, f"{page.locator('.reminder').count()} 則")
    page.screenshot(path=SHOTS / "03_saves.png")
    page.locator(".save-row button").first.click()
    expect(page.locator(".empty:has-text('還沒有收藏')")).to_be_visible(timeout=10000)
    check("取消收藏", page.locator(f".save-row:has-text('{title[:10]}')").count() == 0)

    search_state_reset(page)
    expect(page.locator(".event-card").first).to_be_visible()
    check("找活動不再自動篩選縣市", page.locator("[name=city_id]").input_value() == "")

    print("【數據】")
    page.goto(BASE + "/#/stats")
    expect(page.locator(".hero-number")).to_be_visible()
    check("數據頁只有上架總數、各類別、熱門收藏三塊",
          page.locator(".stats-layout > section").count() == 3 and page.locator(".bar-row").count() == 0)
    check("各類別是向上的長條圖", page.locator(".col").count() >= 8, f"{page.locator('.col').count()} 類")
    page.wait_for_timeout(1500)  # 等動畫跑完
    total_text = page.locator(".hero-number").inner_text().replace(",", "")
    col_sum = sum(int(t.replace(",", "")) for t in page.locator(".col-value").all_inner_texts())
    check("上架總數動畫結束後等於各類別加總", int(total_text) == col_sum, total_text)
    page.locator(".col").first.hover()
    check("長條圖滑鼠提示", page.locator("#tooltip").is_visible() and "場" in page.locator("#tooltip").inner_text())
    check("數據頁沒有說明文字、捲軸和「以表格檢視」",
          "每個場館各算一場" not in page.locator("#app").inner_text() and page.locator(".stat-chart details").count() == 0
          and page.locator(".stat-chart").evaluate("el => el.scrollWidth <= el.clientWidth"))
    check("熱門收藏排行：前三名卡片＋第 4 名以後清單",
          page.locator(".podium li").count() == 3 and page.locator(".top-saves li").count() == 7)
    page.screenshot(path=SHOTS / "04_stats.png", full_page=True)

    print("【登出】")
    page.goto(BASE + "/#/login")
    page.locator("#logout").click()
    page.wait_for_timeout(500)
    check("登出", page.locator("#nav-account").inner_text() == "登入")
    page.goto(BASE + "/#/login")
    demo = page.locator("#demo-login .demo-account")
    check("登入頁的示範帳號是三個按鈕（使用者、商家、管理員）", demo.count() == 3
          and [b.split()[0] for b in demo.all_inner_texts()] == ["使用者", "商家", "管理員"])
    page.locator("[data-tab=register]").click()
    check("註冊分頁不顯示示範帳號", page.locator("#demo-login").is_hidden())
    page.locator("[data-tab=login]").click()
    page.locator("#demo-login .demo-account:has-text('管理員')").click()
    check("點示範帳號直接登入，管理員到管理員後台", waited(lambda: expect(page).to_have_url(BASE + "/#/admin", timeout=10000))
          and page.locator("#nav-account").inner_text() != "登入")
    page.goto(BASE + "/#/login")
    page.locator("#logout").click()
    page.wait_for_timeout(500)

    def login_as(email):
        page.goto(BASE + "/#/login")
        page.locator("#login-form [name=email]").fill(email)
        page.locator("#login-form [name=password]").fill("test1234")
        page.locator("#login-form button").click()
        page.wait_for_timeout(1500)

    print("【商家上架】")
    login_as("merchant@example.com")
    check("商家登入後到商家後台", page.url.endswith("#/merchant") and page.locator("h1").inner_text() == "商家後台")
    page.goto(BASE + "/#/login")
    name_form = page.locator("#name-form")
    check("商家的帳號頁可以修改商家名稱", name_form.locator("label").inner_text().startswith("商家名稱"))
    name_form.locator("[name=name]").fill("光影文創有限公司")
    name_form.locator("button").click()
    check("修改後右上角顯示新的商家名稱",
          waited(lambda: expect(page.locator("#nav-account")).to_have_text("光影文創有限公司", timeout=10000)))
    page.goto(BASE + "/#/search")
    page.locator("[name=keyword]").fill("年度巨星巡迴演唱會")
    page.locator("#filters button.btn-primary").click()
    page.locator(".event-card").first.click()
    check("活動頁顯示商家名稱，不顯示「上架：…・資料來源：…」",
          waited(lambda: expect(page.locator(".detail-head")).to_contain_text("商家：光影文創有限公司", timeout=10000))
          and "資料來源" not in page.locator(".detail").inner_text())
    page.goto(BASE + "/#/merchant")
    page.wait_for_timeout(1500)
    check("商家看不到「我的收藏」選單", not page.locator("[data-nav=saves]").is_visible()
          and page.locator("[data-nav=merchant]").is_visible())
    nav = [a.inner_text() for a in page.locator(".nav a:visible").all()]
    check("商家選單以上架為主：商家後台｜上架新活動｜找活動（沒有首頁、數據）",
          nav[:3] == ["商家後台", "上架新活動", "找活動"] and "首頁" not in nav and "數據" not in nav, "｜".join(nav))
    alert = page.locator(".m-alert")
    check("「上架新活動」是頁面最上面的大按鈕", page.locator(".publish-card").bounding_box()["y"] < alert.bounding_box()["y"]
          and page.locator(".publish-card").bounding_box()["height"] >= 70)
    status_btn = lambda s: page.locator(f".m-status button:has-text('{s}')")
    status_num = lambda s: int(status_btn(s).locator(".m-status-count").inner_text().replace(",", ""))
    check("商家後台沒有「全部」按鈕，四個狀態都在", page.locator(".m-status button").count() == 4
          and page.locator(".m-status button:has-text('全部')").count() == 0)
    check("預設不選狀態、不列活動", page.locator(".m-pick[aria-pressed=true]").count() == 0 and page.locator(".m-item:visible").count() == 0)
    check("可以點的卡片沒有文字提示和箭頭，游標是手指", all("→" not in page.locator(s).inner_text() and "▾" not in page.locator(s).inner_text()
              and "查看" not in page.locator(s).inner_text() and "收起" not in page.locator(s).inner_text() for s in (".m-alert", ".m-overview", ".m-status"))
          and status_btn("上架中").evaluate("el => getComputedStyle(el).cursor") == "pointer")
    check("活動總數的文字靠左，和其他卡片對齊", page.locator(".m-overview .m-stat-label").first.bounding_box()["x"]
          - page.locator(".m-overview .m-pick").bounding_box()["x"] < 40)
    check("活動總數＝四個狀態相加", int(page.locator("#m-total").inner_text().split()[0].replace(",", ""))
          == sum(status_num(s) for s in ["上架中", "待審核", "已退回", "已下架"]))
    check("退回提示顯示被退回的場數", f"{status_num('已退回')} 場活動被退回" in alert.inner_text())
    page.screenshot(path=SHOTS / "07_merchant_overview.png", full_page=True)
    page.locator(".publish-card").evaluate("el => { el.dataset.same = '1'; }")
    status_y = page.locator(".m-status").bounding_box()["y"]
    status_btn("待審核").click()
    running = page.evaluate("document.getAnimations().filter((a) => a instanceof CSSAnimation && a.playState === 'running').length")
    check("點狀態不重畫頁面、不播動畫（不會閃）、版面不跳", running == 0 and page.locator(".publish-card[data-same]").count() == 1
          and page.locator(".m-status").bounding_box()["y"] == status_y, f"動畫 {running} 個")
    alert.click()
    rejected = page.locator(".m-card-rejected:visible")
    check("點退回提示列出被退回的活動：和其他活動一樣的卡片，不另外顯示退回提示", rejected.count() == 1
          and page.locator(".m-item:visible").count() == 1 and rejected.locator(".event-thumb").count() == 1
          and "退回理由" not in rejected.inner_text() and "⚠" not in rejected.inner_text()
          and rejected.locator("a:has-text('修改')").is_visible())
    bg = "el => getComputedStyle(el).backgroundColor"
    check("被退回的卡片顏色和退回提示相同", rejected.evaluate(bg) == alert.evaluate(bg))
    check("點退回提示會選取已退回，提示本身留著", alert.is_visible() and status_btn("已退回").get_attribute("aria-pressed") == "true")
    check("選中的卡片換成主色", status_btn("已退回").evaluate("el => getComputedStyle(el).backgroundColor")
          != status_btn("上架中").evaluate("el => getComputedStyle(el).backgroundColor"))
    status_btn("已退回").click()
    check("再點一次同一個狀態就收起清單", page.locator(".m-item:visible").count() == 0 and page.locator(".m-pick[aria-pressed=true]").count() == 0)
    total_btn = page.locator(".m-overview .m-pick")
    total_btn.click()
    check("點活動總數列出全部活動", page.locator(".m-item:visible").count() == int(page.locator("#m-total").inner_text().split()[0].replace(",", "")))
    order = page.locator(".m-grid > .m-card:visible .m-thumb .tag").all_inner_texts()
    check("看全部時被退回的排最前面，接著是待審核", order[:2] == ["已退回", "待審核"] and rejected.count() == 1, order[:3])
    total_btn.click()
    check("再點一次活動總數就收起清單", page.locator(".m-item:visible").count() == 0)
    status_btn("上架中").click()
    cards = page.locator(".m-grid > .m-card:visible")
    tops = cards.evaluate_all("els => els.map((el) => el.offsetTop)")  # offsetTop 不受浮現動畫的位移影響
    check("其他活動是和找活動一樣的卡片，一行三張", len(tops) >= 3 and len(set(tops[:3])) == 1, tops[:4])
    check("點上架中只列上架中的活動", cards.count() == status_num("上架中")
          and all("上架中" in t for t in cards.locator(".m-thumb .tag").all_inner_texts()))
    saves = {c.locator("h3").inner_text(): int(c.locator(".event-meta").inner_text().split("☆ ")[1].split(" ")[0]) for c in cards.all()}
    top = page.locator("#m-top")
    check("最多收藏整張卡片連到活動頁", (top.get_attribute("href") or "").startswith("#/event/"))
    check("最多收藏顯示收藏數最高的上架中活動", (top.locator(".m-top-title").inner_text() in saves
          and saves[top.locator(".m-top-title").inner_text()] == max(saves.values())
          and f"{max(saves.values())} 人收藏" in top.inner_text()) if max(saves.values()) else "還沒有人收藏" in top.inner_text(),
          top.inner_text().replace("\n", " "))
    camp = page.locator(".m-card:has-text('（測試）寒假天文研習營')")
    check("卡片有圖片、狀態、類別、日期、場館、票價、早鳥截止、修改", camp.locator(".event-thumb").is_visible()
          and "上架中" in camp.locator(".m-thumb .tag").inner_text() and camp.locator(".price").is_visible()
          and "📍" in camp.locator(".event-meta").inner_text()
          and camp.locator(".tag:has-text('早鳥')").count() == 1 and camp.locator("a:has-text('修改')").is_visible())
    check("清單標題不再顯示總收藏人次（每張卡片各自有收藏數）", "人次收藏" not in page.locator(".list-bar").inner_text())
    page.screenshot(path=SHOTS / "07_merchant_home.png", full_page=True)
    page.locator(".publish-card").click()
    copy_from = page.locator("#copy-from")
    expect(copy_from).to_be_visible(timeout=10000)
    source = copy_from.locator("option").nth(1)
    copied = source.inner_text().rsplit("・", 1)[0]
    copy_from.select_option(value=source.get_attribute("value"))
    check("上架表單選「帶入過去活動數據」：名稱、場館帶入，日期空白",
          waited(lambda: expect(page.locator("#event-form [name=title]")).to_have_value(copied, timeout=10000))
          and page.locator("#event-form [name=venue_id]").input_value() != ""
          and page.locator("#event-form [name=start_date]").input_value() == "")
    check("帶入選單在標題同一行右邊、沒有「不帶入」選項",
          abs(copy_from.bounding_box()["y"] - page.locator(".form-head h1").bounding_box()["y"]) < 30
          and copy_from.bounding_box()["x"] > page.locator(".form-head h1").bounding_box()["x"] + 300
          and "不帶入" not in copy_from.inner_text())
    clear = page.locator("#clear-form")
    check("帶入選單寫「帶入過去活動數據」，「清除全部」在選單右邊同一行",
          "帶入過去活動數據" in copy_from.inner_text()
          and clear.bounding_box()["x"] >= copy_from.bounding_box()["x"] + copy_from.bounding_box()["width"]
          and abs((clear.bounding_box()["y"] + clear.bounding_box()["height"] / 2)
                  - (copy_from.bounding_box()["y"] + copy_from.bounding_box()["height"] / 2)) < 6)
    check("上架表單標題下沒有審核流程的說明", page.locator(".form-title p").count() == 0)
    page.locator("#clear-form").click()
    check("按「清除全部」表單回到空白", page.locator("#event-form [name=title]").input_value() == ""
          and page.locator("#event-form [name=venue_id]").input_value() == "" and page.locator("[data-discount]").count() == 0
          and copy_from.input_value() == "")
    page.goto(BASE + "/#/merchant")
    page.locator("[data-nav=merchant-new]").click()
    check("重新進上架表單是空白的", waited(lambda: expect(page.locator("#event-form [name=title]")).to_have_value("", timeout=10000)))
    expect(page.locator("#event-form")).to_be_visible()
    new_title = f"（E2E）週末陶藝工作坊 {uuid.uuid4().hex[:4]}"
    form = page.locator("#event-form")
    form.locator("[name=title]").fill(new_title)
    form.locator("[name=category_id]").select_option(label="工作坊")
    form.locator("#venue-new summary").click()
    venue_name = f"E2E 陶藝教室 {uuid.uuid4().hex[:4]}"
    page.locator("#v-name").fill(venue_name)
    page.locator("#v-city").select_option(label="臺南市")
    page.locator("#v-address").fill("臺南市東區大學路1號")
    page.locator("#v-add").click()
    check("表單內新增場館，並自動選取",
          waited(lambda: expect(form.locator("[name=venue_id] option:checked")).to_contain_text(venue_name, timeout=10000)))
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() + 7 * 86400))
    end = time.strftime("%Y-%m-%d", time.localtime(time.time() + 8 * 86400))
    form.locator("[name=start_date]").fill(start)
    form.locator("[name=end_date]").fill(end)
    form.locator("[name=price]").fill("800")
    form.locator("[name=sale_start]").fill(f"{start}T12:00")
    check("上架表單有活動圖片欄位，預設沒有圖片", "還沒有圖片" in page.locator("#image-preview").inner_text())
    page.locator("#image-file").set_input_files(files=[{"name": "bad.txt", "mimeType": "text/plain", "buffer": b"hello"}])
    check("不是圖片不能上傳", waited(lambda: expect(page.locator("#toast")).to_contain_text("只能上傳", timeout=5000))
          and form.locator("[name=image_url]").input_value() == "")
    page.locator("#image-file").set_input_files(files=[{"name": "cover.png", "mimeType": "image/png", "buffer": TINY_PNG}])
    check("上傳圖片後顯示預覽", waited(lambda: expect(page.locator("#image-preview img")).to_be_visible(timeout=10000))
          and form.locator("[name=image_url]").input_value().startswith("uploads/")
          and page.locator("#image-remove").is_visible())
    page.locator("#add-discount").click()
    row = page.locator("[data-discount]").first
    row.locator("[name=d_type]").select_option(label="早鳥優惠")
    row.locator("[name=d_price]").fill("650")
    form.locator("button.btn-primary").click()
    check("早鳥沒填截止日：顯示資料表驗證規則的錯誤",
          waited(lambda: expect(page.locator("#form-error")).to_contain_text("早鳥", timeout=10000)),
          page.locator("#form-error").inner_text()[:30])
    row.locator("[name=d_end]").fill(start)
    form.locator("button.btn-primary").click()
    page.wait_for_url("**/#/merchant")
    mine = page.locator(f".m-item:has-text('{new_title}'):visible")
    check("送出後在商家後台顯示「待審核」", waited(lambda: expect(mine).to_contain_text("待審核", timeout=10000)))
    page.locator(".m-status button:has-text('已退回')").click()
    page.screenshot(path=SHOTS / "07_merchant_rejected.png")
    page.screenshot(path=SHOTS / "07_merchant.png")
    page.locator(".m-card:has-text('被退回的講座') a:has-text('修改')").click()
    check("按修改後，表單最上面顯示被退回的理由", waited(lambda: expect(page.locator(".reject-note")).to_contain_text("講者", timeout=10000)))
    page.goto(BASE + "/#/merchant")
    expect(page.locator(".publish-card")).to_be_visible(timeout=10000)

    page.locator(".publish-card").click()
    expect(page.locator("#event-form")).to_be_visible()
    form = page.locator("#event-form")
    form.locator("[name=title]").fill("（E2E）城市光影攝影展")
    form.locator("[name=category_id]").select_option(label="展覽")
    form.locator("[name=venue_id]").select_option(label="臺北市・華山1914文化創意產業園區")
    form.locator("[name=start_date]").fill(start)
    form.locator("[name=end_date]").fill(end)
    form.locator("[name=end_date]").dispatch_event("change")
    check("選好場館和日期：列出同場館同期間的已上架活動",
          waited(lambda: expect(page.locator("#venue-overlap")).to_contain_text("（測試）城市光影攝影展", timeout=10000)))
    form.locator("button.btn-primary").click()
    warn = page.locator("#similar-warn")
    check("商家送出前：有相似的已上架活動會提醒", waited(lambda: expect(warn).to_contain_text("（測試）城市光影攝影展", timeout=10000))
          and page.url.endswith("#/merchant/new"))
    page.screenshot(path=SHOTS / "07_merchant_similar.png")
    page.locator("#similar-back").click()
    check("按「回去修改」關掉提醒、留在表單", warn.is_hidden() and page.url.endswith("#/merchant/new"))
    form.locator("button.btn-primary").click()
    expect(warn).to_be_visible(timeout=10000)
    page.locator("#similar-go").click()
    page.wait_for_url("**/#/merchant")
    check("按「仍要送出審核」才送出", waited(lambda: expect(page.locator(".m-item:has-text('（E2E）城市光影攝影展'):visible"))
          .to_contain_text("待審核", timeout=10000)))

    print("【管理員審核】")
    page.goto(BASE + "/#/login")
    page.locator("#logout").click()
    login_as("admin@example.com")
    check("管理員登入後到管理員後台", page.url.endswith("#/admin"))
    nav = [a.inner_text() for a in page.locator(".nav a:visible").all()]
    check("管理員選單：首頁｜管理員後台｜找活動｜數據（管理員後台在首頁右邊）",
          nav[:4] == ["首頁", "管理員後台", "找活動", "數據"], "｜".join(nav))
    item = page.locator(f".queue-item:has-text('{new_title}')")
    panel = page.locator("#review-panel")
    title_in_panel = panel.locator(".review-title h2")
    check("待審核佇列有剛上架的活動", waited(lambda: expect(item).to_have_count(1, timeout=10000)))
    check("分頁顯示待審核場數", page.locator("#pending-count").inner_text().isdigit())
    check("佇列在左、審核面板在右", page.locator(".queue").bounding_box()["x"] + 200 < panel.bounding_box()["x"])
    check("佇列標出快開始的活動", "天後開始" in item.inner_text())
    item.click()
    check("點佇列裡的活動，右邊顯示審核資料",
          waited(lambda: expect(title_in_panel).to_have_text(new_title, timeout=10000)))
    facts = panel.locator(".review-facts").inner_text()
    check("審核面板直接看得到官網、票價、開賣時間、上架者過去的紀錄",
          all(k in facts for k in ["官方網址", "NT$800", "12:00", "其他活動"]), facts.replace("\n", " ")[:80])
    check("審核面板列出優惠", "早鳥優惠" in panel.locator(".review-discounts").inner_text()
          and "NT$650" in panel.locator(".review-discounts").inner_text())
    check("審核面板顯示商家上傳的圖片", panel.locator(".review-thumb img").get_attribute("src").startswith("uploads/"))
    check("沒有相似活動時顯示「沒有偵測到」", panel.locator(".dup-ok").is_visible() and panel.locator(".dup-warn").count() == 0)
    page.screenshot(path=SHOTS / "08_admin.png")
    panel.locator("button:has-text('通過並上架')").click()
    check("通過後從佇列消失", waited(lambda: expect(item).to_have_count(0, timeout=10000)))
    check("處理完自動跳到下一場", waited(lambda: expect(title_in_panel).not_to_have_text(new_title, timeout=10000))
          and page.locator(".queue-item[aria-current=true]").count() == 1)

    dup_item = page.locator(".queue-item:has-text('城市光影 攝影展 2026')")
    check("佇列標題只顯示場數，不顯示排序與統計說明", page.locator(".queue-head").inner_text().strip().endswith("場待審核"))
    check("佇列標出疑似重複", dup_item.locator(".tag:has-text('疑似重複')").count() == 1)
    dup_item.click()
    expect(title_in_panel).to_have_text("（測試）城市光影 攝影展 2026", timeout=10000)
    check("重複提醒：顯示很可能重複的已上架活動", waited(lambda: expect(panel.locator(".dup-warn")).to_contain_text(
          "（測試）城市光影攝影展", timeout=10000)))
    page.screenshot(path=SHOTS / "10_duplicate.png")
    panel.locator("button:has-text('通過並上架')").click()
    check("有相似活動時，通過要按第二次確認", "確定" in panel.locator("button:has-text('通過')").inner_text())
    panel.locator("button:has-text('退回')").click()
    dlg = page.locator("dialog.dialog")
    check("退回彈窗預先勾選「重複上架」並帶入是哪一場",
          waited(lambda: expect(dlg.locator("label.reason:has-text('重複上架') input")).to_be_checked(timeout=5000))
          and "城市光影攝影展" in dlg.locator("[name=note]").input_value())
    dlg.locator("button:has-text('確定退回')").click()
    check("重複的活動退回後從佇列消失", waited(lambda: expect(dup_item).to_have_count(0, timeout=10000)))

    page.locator(".queue-item:has-text('待審核的親子科學營')").click()
    expect(title_in_panel).to_contain_text("待審核的親子科學營", timeout=10000)
    panel.locator("button:has-text('退回')").click()
    dialog = page.locator("dialog.dialog")
    check("按退回跳出選理由的彈窗", waited(lambda: expect(dialog).to_be_visible(timeout=5000))
          and dialog.locator("[name=reason]").count() >= 5)
    dialog.locator("button:has-text('確定退回')").click()
    check("沒選理由不能退回", "理由" in dialog.locator("#reject-error").inner_text() and dialog.is_visible())
    dialog.locator("label.reason:has-text('票價或優惠資訊有誤') input").check()
    dialog.locator("[name=note]").fill("學生價請附證明")
    page.screenshot(path=SHOTS / "09_reject.png")
    dialog.locator("button:has-text('確定退回')").click()
    check("退回後從佇列消失", waited(lambda: expect(page.locator(".queue-item:has-text('待審核的親子科學營')")).to_have_count(0, timeout=10000)))

    print("【管理員活動管理】")
    page.locator("[data-tab=manage]").click()
    pending = page.locator(".admin-row:has-text('待審核的親子科學營')")
    row = page.locator(f".admin-row:has-text('{new_title}')")
    expect(page.locator("#admin-search")).to_be_visible(timeout=10000)
    check("管理員的活動管理保留「全部」", page.locator(".status-tabs button:has-text('全部')").count() == 1)
    page.locator(".status-tabs button:has-text('已退回')").click()
    check("已退回清單顯示退回理由", waited(lambda: expect(pending.locator(".reject-note")).to_contain_text(
          "票價或優惠資訊有誤；補充：學生價請附證明", timeout=10000)))
    page.locator(".status-tabs button:has-text('上架中')").click()
    expect(page.locator(".status-tabs button[aria-selected=true]")).to_contain_text("上架中", timeout=10000)
    page.locator("#admin-search [name=keyword]").fill(new_title)
    page.locator("#admin-search button.btn-primary").click()
    expect(page.locator("#admin-count")).to_have_text("共 1 場", timeout=10000)
    row.locator("button:has-text('違規下架')").click()
    check("違規下架要按第二次確認", "確定" in row.locator("button").first.inner_text())
    row.locator("button").first.click()
    check("違規下架後從上架中清單消失", waited(lambda: expect(row).to_have_count(0, timeout=10000)))
    page.locator(".status-tabs button:has-text('已下架')").click()
    relist = row.locator("button:has-text('重新上架')")
    expect(relist).to_be_visible(timeout=10000)
    relist.click()
    check("重新上架後從已下架清單消失", waited(lambda: expect(row).to_have_count(0, timeout=10000)))
    page.locator("#admin-clear").click()
    page.locator(".status-tabs button:has-text('待審核')").click()
    go = page.locator(".admin-row:has-text('（E2E）城市光影攝影展') button:has-text('前往審核')")
    check("待審核的活動在活動管理不能直接通過，只有「前往審核」",
          waited(lambda: expect(go).to_be_visible(timeout=10000))
          and page.locator(".admin-row:has-text('（E2E）城市光影攝影展') button:has-text('通過')").count() == 0)
    go.click()
    check("按「前往審核」回到審核面板並選好那一場",
          waited(lambda: expect(title_in_panel).to_have_text("（E2E）城市光影攝影展", timeout=10000))
          and page.locator("[data-tab=review]").get_attribute("aria-selected") == "true")
    page.goto(BASE + "/#/login")
    page.locator("#logout").click()
    page.wait_for_timeout(500)
    search_state_reset(page)  # 登出後重新搜尋
    expect(page.locator(".event-card").first).to_be_visible(timeout=15000)
    page.locator("[name=keyword]").fill(new_title)
    page.locator("#filters button.btn-primary").click()
    check("審核通過的活動搜尋得到",
          waited(lambda: expect(page.locator("#result-count")).to_have_text("找到 1 場活動", timeout=10000)))

    print("【手機寬度 400px】")
    phone = browser.new_context(viewport={"width": 400, "height": 860}, device_scale_factor=2, is_mobile=True,
                                has_touch=True, locale="zh-TW")
    mpage = phone.new_page()
    mpage.on("pageerror", lambda e: errors.append(str(e)))
    for name, path in [("首頁", "/#/"), ("找活動", "/#/search"), ("活動詳情", event_url.replace(BASE, "")), ("數據", "/#/stats"), ("登入", "/#/login")]:
        mpage.goto(BASE + path)
        mpage.wait_for_timeout(2500)
        check(f"手機：{name}沒有左右捲動", no_horizontal_scroll(mpage))
        if name == "活動詳情":
            check("手機：票價和收藏按鈕在標題下面、活動介紹前面",
                  mpage.locator(".detail-head").bounding_box()["y"] < mpage.locator(".price-box").bounding_box()["y"]
                  < mpage.locator(".detail .panel").first.bounding_box()["y"])
    mpage.goto(BASE + "/#/")
    mpage.wait_for_timeout(2500)
    mpage.screenshot(path=SHOTS / "05_phone.png")
    mpage.goto(BASE + "/#/search")
    expect(mpage.locator("#results .event-card").first).to_be_visible(timeout=15000)
    mpage.wait_for_timeout(1500)
    first_y = mpage.locator("#results .event-card").first.bounding_box()["y"] + mpage.evaluate("scrollY")
    # 篩選條件全部直接顯示（不收合），卡片會比收合時（約 1,000px 內）後面
    check("手機：第一張活動卡片在篩選條件下面，比最早的版本（約 1,863px）前面", first_y < 1800, f"{first_y:.0f}px")
    mpage.screenshot(path=SHOTS / "05_phone_search.png")
    for email, name, path in [("merchant@example.com", "商家上架表單", "/#/merchant/new"), ("admin@example.com", "管理員後台", "/#/admin")]:
        mpage.goto(BASE + "/#/login")
        mpage.wait_for_timeout(1000)
        if mpage.locator("#logout").count():
            mpage.locator("#logout").click()
        mpage.locator("#login-form [name=email]").fill(email)
        mpage.locator("#login-form [name=password]").fill("test1234")
        mpage.locator("#login-form button").click()
        mpage.wait_for_timeout(1500)
        mpage.goto(BASE + path)
        mpage.wait_for_timeout(2500)
        check(f"手機：{name}沒有左右捲動", no_horizontal_scroll(mpage))
    phone.close()

    print("【深色模式】")
    dark = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="dark", locale="zh-TW")
    dpage = dark.new_page()
    dpage.goto(BASE + "/#/")
    dpage.wait_for_timeout(2500)
    bg = dpage.evaluate("getComputedStyle(document.body).backgroundColor")
    check("深色模式背景是深色", bg == "rgb(15, 23, 32)", bg)
    dark.close()
    light = browser.new_context(viewport={"width": 1280, "height": 900}, color_scheme="light", locale="zh-TW")
    lpage = light.new_page()
    lpage.goto(BASE + "/#/")
    lpage.wait_for_timeout(2500)
    check("淺色模式背景是淺色", lpage.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(247, 244, 238)")
    lpage.screenshot(path=SHOTS / "06_light.png")
    light.close()

    check("瀏覽器沒有 JavaScript 錯誤", not errors, "；".join(errors[:3]))
    browser.close()


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp())
    db_copy = test_db.build(tmp / "e2e.accdb")
    server = start_server(db_copy)
    try:
        with sync_playwright() as p:
            run(p)
    except Exception as exc:
        check("測試流程沒有中斷", False, f"{type(exc).__name__}: {str(exc)[:300]}")
    finally:
        server.terminate()
        server.wait(timeout=10)
        shutil.rmtree(tmp, ignore_errors=True)
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}／{len(results)} 項通過" + ("，全部通過" if not failed else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
