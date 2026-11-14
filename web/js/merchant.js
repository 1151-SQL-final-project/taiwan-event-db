// 商家後台：總覽、我的活動。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 商家後台 ----------

const merchant = { status: "" };

// 商家後台：最上面是退回提示，接著是活動總數、最多收藏和四個狀態；
// 預設不列活動，點活動總數（全部）或狀態才在下面列出，再點一次收起。活動都用和找活動一樣的卡片（一行三張），被退回的換成提示的顏色；
// 看全部時把要處理的排前面：已退回 → 待審核 → 上架中 → 已下架；同一個狀態裡，開賣或早鳥截止近的排前面
const MERCHANT_ALL = "全部";
const MERCHANT_ORDER = { "已退回": 0, "待審核": 1, "上架中": 2, "已下架": 3 };
function merchantSortKey(e) {
  const soon = [notOnSale(e.EventSaleStartDate) ? e.EventSaleStartDate : null, e.EarlyBirdEnd].filter(Boolean).sort()[0];
  return [MERCHANT_ORDER[e.EventStatus] ?? 9, soon ? 0 : 1, (soon ?? e.EventStartDate).slice(0, 16)];
}
function compareKeys(a, b) {
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  return 0;
}

async function viewMerchant() {
  if (!requireRole("商家", "#/merchant")) return;
  app.innerHTML = '<div class="skeleton" style="min-height: 320px"></div>';
  const [events, summary] = await Promise.all([api("/api/merchant/events"), api("/api/merchant/summary").catch(() => null)]);
  if (routeNow() !== "#/merchant") return;
  // 分頁的場數由後端 GROUP BY 審核狀態算出；摘要載入失敗時改用清單自己數
  const by = Object.fromEntries((summary?.by_status ?? []).map((r) => [r.EventStatus, r]));
  const counts = Object.fromEntries(["待審核", "上架中", "已退回", "已下架"].map((s) =>
    [s, summary ? by[s]?.EventCount ?? 0 : events.filter((e) => e.EventStatus === s).length]));
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  // 最多收藏只看上架中的活動（其他狀態使用者看不到、也收藏不了）；同數時取清單裡先出現的
  const top = events.filter((e) => e.EventStatus === "上架中" && e.SaveCount > 0)
    .reduce((best, e) => (!best || e.SaveCount > best.SaveCount ? e : best), null);
  const sorted = events.map((e) => [merchantSortKey(e), e]).sort(([a], [b]) => compareKeys(a, b)).map(([, e]) => e);
  const pick = (s) => `aria-pressed="${s === merchant.status}"`;
  app.innerHTML = `
    <h1>商家後台</h1>
    ${counts["已退回"] ? `<button type="button" class="m-alert">
      <span class="m-alert-text"><b>⚠ 有 ${counts["已退回"]} 場活動被退回</b><span>修改後可以重新送審</span></span></button>` : ""}
    <h2 class="list-bar">我的活動</h2>
    <div class="m-overview">
      <button type="button" class="card m-stat m-pick" data-status="${MERCHANT_ALL}" ${pick(MERCHANT_ALL)}>
        <span class="m-stat-label">活動總數</span>
        <span class="m-stat-value" id="m-total">${total.toLocaleString("zh-TW")} <small>場</small></span></button>
      ${top ? `<a class="card m-stat m-top-link" id="m-top" href="#/event/${top.EventID}"><span class="m-stat-label">最多收藏</span>
        <span class="m-top-title">${esc(top.EventTitle)}</span>
        <span class="m-top-count">☆ ${top.SaveCount.toLocaleString("zh-TW")} 人收藏</span></a>`
        : `<div class="card m-stat" id="m-top"><span class="m-stat-label">最多收藏</span>
        <span class="m-top-empty">上架中的活動還沒有人收藏</span></div>`}
    </div>
    <div class="m-status" role="group" aria-label="依審核狀態查看活動">${Object.keys(counts).map((s) => `
      <button type="button" class="m-pick" data-status="${esc(s)}" ${pick(s)}>
        <span class="m-status-count">${counts[s].toLocaleString("zh-TW")}</span><span class="m-status-name">${esc(s)}</span></button>`).join("")}</div>
    <div id="m-list">
      ${sorted.length ? `<div class="grid m-grid">${sorted.map(merchantCard).join("")}</div>` : ""}
      <div class="card empty" id="m-empty" hidden>這個狀態沒有活動。</div>
      ${events.length ? "" : '<div class="card empty">還沒有上架活動。按上方「上架新活動」開始。</div>'}
    </div>`;
  const list = app.querySelector("#m-list");
  // 活動一次全部放進頁面，切換時只顯示／隱藏：不用重畫整頁，就不會閃，圖片也不用重新載入
  list.querySelectorAll("img").forEach((img) => { img.loading = "eager"; });
  const applyStatus = () => {
    const all = merchant.status === MERCHANT_ALL;
    const items = [...list.querySelectorAll(".m-item")];
    items.forEach((el) => { el.hidden = !(all || el.dataset.eventStatus === merchant.status); });
    list.querySelectorAll(".m-grid").forEach((grid) => { grid.hidden = !grid.querySelector(".m-item:not([hidden])"); });
    list.querySelector("#m-empty").hidden = !(events.length && merchant.status && items.every((el) => el.hidden));
    app.querySelectorAll(".m-pick").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.status === merchant.status)));
  };
  app.querySelectorAll(".m-pick").forEach((b) => b.addEventListener("click", () => {
    merchant.status = merchant.status === b.dataset.status ? "" : b.dataset.status;
    applyStatus();
  }));
  // 退回提示：一定是打開已退回（不會收起），手機上清單可能在畫面外，捲過去
  app.querySelector(".m-alert")?.addEventListener("click", () => {
    merchant.status = "已退回";
    applyStatus();
    list.scrollIntoView({ block: "nearest", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
  applyStatus();
}

// 和找活動的活動卡片一樣（圖片、類別、票價、日期、場館），左上角加審核狀態，下方加收藏數
function merchantCard(e) {
  const p = priceView(e.EventOriginalPrice, e.BestDiscountPrice, e.EventURL);
  return `<article class="card event-card m-card m-item ${e.EventStatus === "已退回" ? "m-card-rejected" : ""}" data-event-status="${esc(e.EventStatus)}">
    <a class="m-thumb" href="#/event/${e.EventID}" tabindex="-1" aria-hidden="true">${eventThumb(e)}${statusTag(e.EventStatus)}</a>
    <div class="event-body">
      <div><span class="tag">${esc(e.CategoryName)}</span> ${p.tag ?? ""} ${saleTag(e.EventSaleStartDate)}
        ${e.EarlyBirdEnd ? `<span class="tag tag-deal">早鳥 ${esc(fmtDay(e.EarlyBirdEnd))} 截止</span>` : ""}</div>
      <h3><a href="#/event/${e.EventID}">${esc(e.EventTitle)}</a></h3>
      <div class="event-meta">
        <div>📅 ${fmtRange(e.EventStartDate, e.EventEndDate)}</div>
        <div>📍 ${esc(`${e.CityName}・${e.VenueName}`)}</div>
        <div>☆ ${e.SaveCount} 人收藏・優惠 ${e.DiscountCount} 筆</div>
      </div>
      <div class="price-row">
        <span class="price ${p.muted ? "muted" : ""}">${esc(p.main)}</span>
        ${p.old ? `<span class="price-old">${esc(p.old)}</span>` : ""}
      </div>
    </div>
  </article>`;
}
