// 探點：單頁式網頁。網址 # 後面決定顯示哪一頁：
//   #/ 首頁　#/search 找活動　#/event/12 活動詳情　#/saves 我的收藏　#/stats 數據　#/login 登入／註冊
// 三種角色：使用者（查詢、收藏）、商家（上架、修改自己的活動）、管理員（審核、下架、統計）。
// 畫面上依角色顯示不同選單，但真正的權限檢查在後端（api/common.py 的 require_role）。
//
// 網頁程式分成 web/js/ 裡的幾個檔案（index.html 依序載入）：
//   core.js 共用工具與 API　cards.js 活動卡片與插圖　home.js　search.js　event.js　saves.js　stats.js
//   auth.js 登入與註冊　app.js（本檔）路由與啟動，最後載入

// ---------- 路由 ----------

const routes = [
  [/^#\/?$/, viewHome, "home"],
  [/^#\/search$/, viewSearch, "search"],
  [/^#\/event\/(\d+)$/, viewEvent, null],
  [/^#\/saves$/, viewSaves, "saves"],
  [/^#\/stats$/, viewStats, "stats"],
  [/^#\/login$/, viewLogin, "login"],
];

async function router() {
  const hash = location.hash || "#/";
  const [pattern, view, nav] = routes.find(([re]) => re.test(hash)) ?? routes[0];
  document.querySelectorAll("[data-nav]").forEach((a) => a.dataset.nav === nav ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"));
  try {
    await view(...(hash.match(pattern) ?? []).slice(1));
  } catch (err) {
    app.innerHTML = `<div class="card empty"><h2>出了點問題</h2><p>${esc(err.message)}</p><a class="btn" href="#/">回首頁</a></div>`;
  }
}

// ---------- 啟動 ----------

window.addEventListener("hashchange", router);
loadMe().then(router);
