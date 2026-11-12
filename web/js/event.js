// 活動詳情：票價、優惠、場次、收藏。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 活動詳情 ----------

async function viewEvent(id) {
  search.scrollY = window.scrollY;
  app.innerHTML = '<div class="skeleton" style="min-height: 320px"></div>';
  const here = routeNow();
  const e = await api(`/api/events/${id}`);
  if (routeNow() !== here) return;
  const valid = e.Discounts.filter((d) => d.IsValidNow);
  const best = valid.length ? Math.min(...valid.map((d) => d.DiscountPrice)) : null;
  const p = priceView(e.EventOriginalPrice, best, e.EventURL);
  const saved = savedIds.has(e.EventID);
  const longText = (e.EventDescription || "").length > 600;
  const isOwner = me && me.UserID === e.EventOrganizer_FK && me.UserRole === "商家";
  const canSave = !me || me.UserRole === "使用者";
  const back = isOwner ? ["#/merchant", "← 回商家後台"] : me?.UserRole === "管理員" && e.EventStatus !== "上架中"
    ? ["#/admin", "← 回管理員後台"] : ["#/search", "← 回搜尋結果"];

  app.innerHTML = `
    <a class="back btn-text" href="${back[0]}">${back[1]}</a>
    ${e.EventStatus !== "上架中" ? `<div class="notice">這場活動目前是 ${statusTag(e.EventStatus)}，還沒有公開。</div>` : ""}
    <div class="detail">
      <div class="detail-main">
        <section class="card detail-head">
          ${e.EventImageURL ? `<div class="detail-cover"><img src="${esc(e.EventImageURL)}" alt="${esc(e.EventTitle)} 主視覺" referrerpolicy="no-referrer" data-cover></div>` : ""}
          <div class="tags"><span class="tag">${esc(e.CategoryName)}</span><span class="tag">${esc(e.CategoryGroup)}</span>${p.tag ?? ""}</div>
          <h1>${esc(e.EventTitle)}</h1>
          ${e.OrganizerRole === "商家" ? `<div class="muted">🏪 商家：${esc(e.OrganizerName)}</div>` : ""}
          <div class="muted">📅 ${fmtDay(e.EventStartDate, true)}${ymd(toDate(e.EventStartDate)) === ymd(toDate(e.EventEndDate)) ? "" : ` – ${fmtDay(e.EventEndDate, true)}`}</div>
        </section>
        ${sessionsPanel(e.EventShowTimes)}
        <section class="card panel">
          <h2>地點</h2>
          <div class="session-time">${esc(e.VenueName)} <span class="tag">${esc(e.CityName)}</span> <span class="tag">${esc(e.CityRegion)}</span></div>
          <div class="muted small"><a href="${esc(e.GoogleMapsAddressURL)}" target="_blank" rel="noopener" title="用地址在 Google 地圖定位">${esc(e.VenueAddress)}</a>・<a href="${esc(e.GoogleMapsURL)}" target="_blank" rel="noopener">在 Google 地圖開啟 ↗</a></div>
        </section>
        ${e.EventDescription ? `
        <section class="card panel">
          <h2>活動介紹</h2>
          <div class="description ${longText ? "clamped" : ""}" id="desc">${esc(e.EventDescription)}</div>
          ${longText ? '<button class="btn-text" id="desc-toggle">展開全文</button>' : ""}
        </section>` : ""}
      </div>
      <aside class="side">
        <section class="card price-box">
          <div class="muted small">${best !== null && p.old ? "優惠價" : "票價"}</div>
          <div><span class="price-big ${p.muted ? "muted" : ""}">${esc(p.main)}</span>
            ${p.old ? `<span class="price-old">原價 ${esc(p.old)}</span>` : ""}</div>
          ${e.EventSaleStartDate ? `<div class="sale-info ${notOnSale(e.EventSaleStartDate) ? "upcoming" : ""}">
            ${notOnSale(e.EventSaleStartDate) ? `🎫 <b>${esc(fmtTime(e.EventSaleStartDate))} 開賣</b>
              <div class="small">${saleCountdown(e.EventSaleStartDate)}${canSave ? "，收藏後會在「我的收藏」提醒你" : ""}</div>`
              : `<span class="small">已開賣（${esc(fmtTime(e.EventSaleStartDate))} 起）</span>`}</div>` : ""}
          ${canSave && e.EventStatus === "上架中" ? `<button class="btn ${saved ? "btn-saved" : "btn-primary"}" id="save-btn">${saved ? "✓ 已收藏" : "☆ 收藏活動"}</button>` : ""}
          ${isOwner ? `<a class="btn btn-primary" href="#/merchant/edit/${e.EventID}">修改活動</a>` : ""}
          ${e.EventURL ? `<a class="btn" href="${esc(e.EventURL)}" target="_blank" rel="noopener">活動官網 ↗</a>` : ""}
        </section>
        <section class="card panel">
          <h2>優惠</h2>
          <ul class="list">${e.Discounts.map((d) => `
            <li class="discount ${d.IsValidNow ? "" : "expired"}">
              <div><span class="tag ${d.IsValidNow ? "tag-deal" : ""}">${esc(d.DiscountTypeName)}</span>
                <div class="small">${esc(d.DiscountDescription || "")}</div>
                <div class="muted small">${d.IsValidNow ? (d.DiscountEndDate ? `${fmtDay(d.DiscountEndDate)} 截止` : "無截止日") : "已失效"}</div></div>
              <div class="amount">${money(d.DiscountPrice)}</div>
            </li>`).join("") || '<li class="muted small">目前沒有登錄優惠</li>'}
          </ul>
        </section>
      </aside>
    </div>`;

  document.getElementById("desc-toggle")?.addEventListener("click", (ev) => {
    const clamped = document.getElementById("desc").classList.toggle("clamped");
    ev.target.textContent = clamped ? "展開全文" : "收合";
  });
  document.getElementById("sessions-more")?.addEventListener("click", (ev) => {
    app.querySelectorAll(".session-list [hidden]").forEach((li) => { li.hidden = false; });
    ev.target.remove();
  });
  document.getElementById("save-btn")?.addEventListener("click", () => toggleSave(e.EventID));
  window.scrollTo(0, 0);
}

// 場次時間：EventShowTimes 是「開始|結束;開始|結束」。優先列還沒結束的場次
function sessionLines(text) {
  if (!text) return [];
  const all = text.split(";").map((s) => s.split("|"));
  const now = new Date(), left = all.filter(([start, end]) => toDate(end || start) >= now);
  return left.length ? left : all;
}
const clock = (iso) => { const t = iso.slice(11, 16); return t === "00:00" ? "" : t; };
function fmtSession([start, end]) {
  if (!end || end === start) return `${fmtDay(start)} ${clock(start)}`.trim();
  if (start.slice(0, 10) === end.slice(0, 10)) return `${fmtDay(start)} ${[clock(start), clock(end)].filter(Boolean).join("–")}`.trim();
  return `${fmtDay(start)} ${clock(start)} – ${fmtDay(end)} ${clock(end)}`.replace(/\s+/g, " ").trim();
}
const SESSIONS_FIRST = 6;
function sessionsPanel(text) {
  const lines = sessionLines(text);
  // 只有一段而且沒有時、分時，和上面的活動日期一樣，不用重複顯示
  if (!lines.length || (lines.length === 1 && !clock(lines[0][0]) && !clock(lines[0][1] || lines[0][0]))) return "";
  return `<section class="card panel">
    <h2>場次時間</h2>
    <ul class="session-list">${lines.map((l, i) => `<li ${i >= SESSIONS_FIRST ? "hidden" : ""}>${esc(fmtSession(l))}</li>`).join("")}</ul>
    ${lines.length > SESSIONS_FIRST ? `<button type="button" class="btn-text" id="sessions-more">顯示全部 ${lines.length} 場</button>` : ""}
  </section>`;
}

function saleCountdown(iso) {
  const ms = toDate(iso) - new Date();
  const days = Math.floor(ms / 86400000), hours = Math.floor((ms % 86400000) / 3600000);
  return days > 0 ? `還有 ${days} 天 ${hours} 小時` : hours > 0 ? `還有 ${hours} 小時` : "快開賣了";
}

async function toggleSave(eventId) {
  if (!me) { location.hash = "#/login"; viewLogin.returnTo = `#/event/${eventId}`; toast("登入後就能收藏"); return; }
  const btn = document.getElementById("save-btn");
  btn.disabled = true;
  try {
    if (savedIds.has(eventId)) {
      await api(`/api/saves/${eventId}`, { method: "DELETE" });
      savedIds.delete(eventId);
      toast("已取消收藏");
    } else {
      await api(`/api/saves/${eventId}`, { method: "POST" });
      savedIds.add(eventId);
      toast("已加入收藏");
    }
    const saved = savedIds.has(eventId);
    btn.className = `btn ${saved ? "btn-saved" : "btn-primary"} pop`;
    btn.textContent = saved ? "✓ 已收藏" : "☆ 收藏活動";
    btn.addEventListener("animationend", () => btn.classList.remove("pop"), { once: true });
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}
