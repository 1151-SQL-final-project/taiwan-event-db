// 管理員後台：待審核佇列與審核面板。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 管理員後台 ----------
// 管理員最常做的是審核：左邊是待審核佇列、右邊是審核需要的全部資料（官網、票價、優惠、介紹、重複提醒、上架者紀錄），
// 不用一場一場點進活動頁再回來；處理完自動跳到下一場。

const admin = { queue: [], current: null, similar: {} };
// 每個狀態可以做的操作：[新狀態, 按鈕文字, 是否要再按一次確認]
const ADMIN_ACTIONS = {
  "待審核": [["上架中", "通過並上架", false]],
};
const SOON_DAYS = 7;
const today0 = () => new Date(new Date().toDateString());
// 距離活動開始還有幾天（負數 = 已經開始）
const daysUntil = (iso) => Math.round((toDate(isoDay(iso)) - today0()) / 864e5);
function startTag(e) {
  if (toDate(e.EventEndDate) < today0()) return '<span class="tag">已結束</span>';
  const d = daysUntil(e.EventStartDate);
  if (d > SOON_DAYS) return "";
  return `<span class="tag tag-sale">${d < 0 ? "已開始" : d === 0 ? "今天開始" : `${d} 天後開始`}</span>`;
}

async function viewAdmin() {
  if (!requireRole("管理員", "#/admin")) return;
  app.innerHTML = `
    <div class="page-head">
      <h1>管理員後台</h1>
    </div>
    <div id="admin-body"></div>`;
  adminQueue();
}

// ----- 待審核：佇列＋審核面板 -----

async function adminQueue(selectId = null) {
  const body = document.getElementById("admin-body");
  body.innerHTML = '<div class="skeleton" style="min-height: 320px"></div>';
  const data = await api(`/api/admin/events?status=${encodeURIComponent("待審核")}&page_size=200`);
  if (routeNow() !== "#/admin" || !body.isConnected) return;
  if (data.auto_offlined) toast(`自動下架 ${data.auto_offlined} 場已結束的活動`);
  admin.queue = data.items;
  admin.queue.forEach((e) => { admin.similar[e.EventID] = e.Similar ?? []; });
  if (!admin.queue.length) {
    body.innerHTML = `<div class="card empty queue-done">
      <b>✓ 待審核的活動都處理完了</b></div>`;
    return;
  }
  body.innerHTML = `
    <div class="review">
      <aside class="card queue" aria-label="待審核佇列">
        <div class="queue-head">
          <b>${data.total} 場待審核</b>
        </div>
        <ol class="queue-list">${admin.queue.map((e) => `
          <li><button type="button" class="queue-item" data-pick="${e.EventID}">
            <span class="queue-title">${esc(e.EventTitle)}</span>
            <span class="muted small">${esc(e.CategoryName)}・${fmtRange(e.EventStartDate, e.EventEndDate)}・${esc(e.CityName)}</span>
            <span class="queue-meta"><span class="muted small">${esc(e.OrganizerName)}</span>
              ${e.Similar?.length ? `<span class="tag ${e.Similar.some((s) => s.Level === "很可能重複") ? "tag-deal" : "tag-warn"}">疑似重複</span>` : ""}
              ${startTag(e)}</span>
          </button></li>`).join("")}
        </ol>
      </aside>
      <section class="card review-panel" id="review-panel" aria-live="polite"></section>
    </div>`;
  body.querySelector(".queue-list").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-pick]");
    if (b) selectReview(Number(b.dataset.pick), true);
  });
  const first = admin.queue.find((e) => e.EventID === selectId) ?? admin.queue[0];
  selectReview(first.EventID);
}

async function selectReview(id, byUser = false) {
  admin.current = id;
  document.querySelectorAll("[data-pick]").forEach((b) => b.setAttribute("aria-current", Number(b.dataset.pick) === id));
  const panel = document.getElementById("review-panel");
  panel.innerHTML = '<div class="skeleton" style="min-height: 360px"></div>';
  const r = await api(`/api/admin/events/${id}/review`);
  if (admin.current !== id || !panel.isConnected) return;
  admin.similar[id] = r.similar;
  panel.innerHTML = reviewPanel(r);
  panel.querySelector(".review-actions").addEventListener("click", adminAction);
  // 手機上佇列在面板上面，點選後捲到面板（內容載入後才捲，才捲得到；扣掉固定在上面的選單列）
  if (byUser && matchMedia("(max-width: 900px)").matches) {
    window.scrollTo({ top: panel.getBoundingClientRect().top + scrollY - document.querySelector(".topbar").offsetHeight - 12, behavior: "smooth" });
  }
}

function organizerHistory(rows) {
  if (!rows.length) return '<span class="tag tag-warn">第一次上架</span>';
  const by = Object.fromEntries(rows.map((r) => [r.EventStatus, r.EventCount]));
  return ["上架中", "待審核", "已退回", "已下架"].filter((s) => by[s])
    .map((s) => (s === "已退回" ? `<b class="history-rejected">已退回 ${by[s]}</b>` : `${s} ${by[s]}`)).join("・");
}

function discountPeriod(d) {
  if (!d.DiscountStartDate && !d.DiscountEndDate) return "無期限";
  return `${d.DiscountStartDate ? fmtDay(d.DiscountStartDate) : ""} – ${d.DiscountEndDate ? fmtDay(d.DiscountEndDate) : "無截止日"}`;
}

function reviewPanel({ event: e, similar, organizer_history: history }) {
  const p = priceView(e.EventOriginalPrice, null, e.EventURL);
  const sessions = sessionLines(e.EventShowTimes);
  const showSessions = sessions.length > 1 || (sessions.length === 1 && !!clock(sessions[0][0]));
  const actions = (ADMIN_ACTIONS[e.EventStatus] ?? []).filter(([to]) => !(to === "上架中" && e.IsEnded));
  return `
    <div class="review-head">
      <div class="review-thumb">${eventThumb(e)}</div>
      <div class="review-title">
        <div class="tags"><span class="tag">${esc(e.CategoryName)}</span>${statusTag(e.EventStatus)}${startTag(e)}</div>
        <h2>${esc(e.EventTitle)}</h2>
        <div class="muted small">編號 ${e.EventID}・資料來源：${esc(e.EventDataSource)}</div>
      </div>
    </div>
    ${similar.length ? similarBox(similar) : '<div class="dup-ok">✓ 沒有偵測到日期重疊、名稱相似的其他活動</div>'}
    <dl class="review-facts">
      <div><dt>官方網址</dt><dd>${e.EventURL ? `<a href="${esc(e.EventURL)}" target="_blank" rel="noopener">${esc(e.EventURL)} ↗</a>`
        : '<span class="fact-missing">沒有填，無法對照官網查證</span>'}</dd></div>
      <div><dt>日期</dt><dd>${fmtRange(e.EventStartDate, e.EventEndDate)}
        ${showSessions ? `<div class="muted small">場次：${sessions.slice(0, 3).map((l) => esc(fmtSession(l))).join("、")}${sessions.length > 3 ? ` 等 ${sessions.length} 場` : ""}</div>` : ""}</dd></div>
      <div><dt>地點</dt><dd>${esc(e.CityName)}・${esc(e.VenueName)}<div class="muted small">${esc(e.VenueAddress || "")}</div></dd></div>
      <div><dt>票價</dt><dd class="${p.muted ? "muted" : ""}">${esc(p.main)}</dd></div>
      <div><dt>開賣時間</dt><dd>${e.EventSaleStartDate ? esc(fmtTime(e.EventSaleStartDate)) : '<span class="muted">沒有填（視為已開賣）</span>'}</dd></div>
      <div><dt>上架者</dt><dd>${esc(e.OrganizerName)}（${esc(e.OrganizerRole)}）<div class="small">其他活動：${organizerHistory(history)}</div></dd></div>
    </dl>
    <h3 class="review-sub">優惠 <span class="muted small">${e.Discounts.length} 筆</span></h3>
    ${e.Discounts.length ? `<ul class="review-discounts">${e.Discounts.map((d) => `
      <li><span class="tag tag-deal">${esc(d.DiscountTypeName)}</span> <b>${money(d.DiscountPrice)}</b>
        <span class="muted small">${discountPeriod(d)}</span>
        ${e.EventOriginalPrice !== null && d.DiscountPrice >= e.EventOriginalPrice ? '<span class="fact-missing small">沒有比原價便宜</span>' : ""}
        ${d.DiscountDescription ? `<div class="muted small">${esc(d.DiscountDescription)}</div>` : ""}</li>`).join("")}</ul>`
      : '<p class="muted small">沒有登錄優惠</p>'}
    <h3 class="review-sub">活動介紹</h3>
    ${e.EventDescription ? `<div class="description review-desc">${esc(e.EventDescription)}</div>` : '<p class="fact-missing small">沒有填活動介紹</p>'}
    <div class="review-actions">
      ${actions.map(([to, label, confirm]) => adminButton(e, to, label, confirm || (to === "上架中" && similar.length > 0), "review")).join("")}
      ${e.IsEnded && e.EventStatus === "待審核" ? '<span class="muted small">活動已結束，不能上架，請退回</span>' : ""}
      <a class="btn-text review-open" href="#/event/${e.EventID}" target="_blank" rel="noopener">在新分頁看活動頁 ↗</a>
    </div>`;
}

const adminButton = (e, to, label, confirm, ctx) =>
  `<button class="btn ${to === "上架中" ? "btn-primary" : ""}" data-to="${to}" data-id="${e.EventID}" data-ctx="${ctx}"
    data-title="${esc(e.EventTitle)}" data-label="${label}" ${confirm ? "data-confirm" : ""}>${label}</button>`;

// 審核時的重複提醒：日期重疊、名稱相似（加上同場館或同縣市）的其他已上架或待審核活動（規則見 api/similar.py）
function similarBox(list) {
  const likely = list.some((s) => s.Level === "很可能重複");
  return `<div class="dup-warn ${likely ? "likely" : ""}" role="note">
    <b>⚠ 偵測到 ${list.length} 場${likely ? "很可能重複" : "相似"}的活動</b>，通過前請確認是不是重複上架：
    ${similarList(list)}</div>`;
}

function similarList(list) {
  return `<ul>${list.map((s) => `<li>
      <span class="tag ${s.Level === "很可能重複" ? "tag-deal" : "tag-warn"}">${esc(s.Level)}</span>
      <a href="#/event/${s.EventID}" target="_blank" rel="noopener">${esc(s.EventTitle)}</a> ${statusTag(s.EventStatus)}
      <div class="muted small">${fmtRange(s.EventStartDate, s.EventEndDate)}・${esc(s.CityName)} ${esc(s.VenueName)}・上架：${esc(s.OrganizerName)}
        ・${s.Reasons.map(esc).join("、")}</div></li>`).join("")}</ul>`;
}

async function adminAction(ev) {
  const btn = ev.target.closest("[data-to]");
  if (!btn) return;
  // 有相似活動時的通過要再按一次確認（不用瀏覽器的 confirm 對話框）
  if (btn.hasAttribute("data-confirm") && !btn.dataset.armed) {
    btn.dataset.armed = "1";
    btn.textContent = `確定${btn.dataset.label}？`;
    btn.classList.add("btn-danger");
    setTimeout(() => { if (btn.isConnected) { delete btn.dataset.armed; btn.textContent = btn.dataset.label; btn.classList.remove("btn-danger"); } }, 4000);
    return;
  }
  const id = Number(btn.dataset.id);
  btn.disabled = true;
  try {
    const r = await api(`/api/admin/events/${id}/status`, { method: "POST", body: JSON.stringify({ status: btn.dataset.to }) });
    toast(`已${r.action}「${btn.dataset.title}」`);
    // 處理完跳到佇列裡的下一場（最後一場就跳到前一場）
    const i = admin.queue.findIndex((e) => e.EventID === id);
    adminQueue((admin.queue[i + 1] ?? admin.queue[i - 1])?.EventID ?? null);
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
}
