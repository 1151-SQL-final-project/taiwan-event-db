// 我的收藏：收藏清單、優惠截止與開賣提醒。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 我的收藏 ----------

async function viewSaves() {
  if (!me) {
    app.innerHTML = `<div class="card empty"><h2>登入後查看收藏</h2><p>收藏的活動和優惠截止提醒都會在這裡。</p>
      <a class="btn btn-primary" href="#/login">登入／註冊</a></div>`;
    viewLogin.returnTo = "#/saves";
    return;
  }
  if (me.UserRole !== "使用者") {
    app.innerHTML = `<div class="card empty"><h2>收藏功能只開放給使用者帳號</h2>
      <p>${esc(me.UserRole)}帳號請到${me.UserRole === "商家" ? '<a href="#/merchant">商家後台</a>' : '<a href="#/admin">管理員後台</a>'}。</p></div>`;
    return;
  }
  const [saves, reminders, sales] = await Promise.all([
    api("/api/saves"), api("/api/saves/reminders?days=14"), api("/api/saves/sale-reminders?days=14")]);
  if (routeNow() !== "#/saves") return;
  savedIds = new Set(saves.map((s) => s.EventID));
  app.innerHTML = `
    <h1>我的收藏</h1>
    ${sales.length ? `<section style="margin-bottom: 10px">${sales.map((r) => `
      <a class="reminder reminder-sale" href="#/event/${r.EventID}">🎫 <span><b>${r.DaysLeft === 0 ? "今天" : `${r.DaysLeft} 天後`}開賣</b>：
        ${esc(r.EventTitle)}（${esc(fmtTime(r.EventSaleStartDate))}）</span></a>`).join("")}</section>` : ""}
    ${reminders.length ? `<section style="margin-bottom: 18px">${reminders.map((r) => `
      <a class="reminder" href="#/event/${r.EventID}">⏰ <span><b>${r.DaysLeft === 0 ? "今天" : `${r.DaysLeft} 天後`}截止</b>：
        ${esc(r.EventTitle)} 的${esc(r.DiscountTypeName)}（${money(r.DiscountPrice)}）</span></a>`).join("")}</section>` : ""}
    <section class="card">${saves.length ? saves.map((s) => `
      <div class="save-row ${s.EventStatus === "上架中" ? "" : "is-off"}">
        ${s.EventStatus === "上架中" ? `<a class="save-thumb" href="#/event/${s.EventID}" tabindex="-1" aria-hidden="true">${eventThumb(s)}</a>`
          : `<div class="save-thumb" aria-hidden="true">${eventThumb(s)}</div>`}
        <div style="min-width: 0">
          ${s.EventStatus === "上架中" ? `<a href="#/event/${s.EventID}">${esc(s.EventTitle)}</a>`
            : `<span class="save-title">${esc(s.EventTitle)}</span> ${statusTag(s.EventStatus)}`}
          <div class="muted small">${esc(s.CategoryName)}・${fmtRange(s.EventStartDate, s.EventEndDate)}・${esc(s.CityName)}・收藏於 ${fmtDay(s.SaveDate)}</div>
          ${notOnSale(s.EventSaleStartDate) ? `<div class="small">${saleTag(s.EventSaleStartDate)}</div>` : ""}
        </div>
        <button class="btn" data-unsave="${s.EventID}">取消收藏</button>
      </div>`).join("") : '<div class="empty">還沒有收藏。看到喜歡的活動，在活動頁按「收藏活動」。<br><br><a class="btn btn-primary" href="#/search">去找活動</a></div>'}
    </section>`;
  app.querySelectorAll("[data-unsave]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    await api(`/api/saves/${b.dataset.unsave}`, { method: "DELETE" });
    toast("已取消收藏");
    viewSaves();
  }));
}
