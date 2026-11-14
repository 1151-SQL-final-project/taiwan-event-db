// 商家後台：總覽、我的活動、上架與修改表單。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 商家後台 ----------

const merchant = { status: "" };

// 商家後台：最上面是「上架新活動」和退回提示，接著是活動總數、最多收藏和四個狀態；
// 預設不列活動，點活動總數（全部）或狀態才在下面列出，再點一次收起。活動都用和找活動一樣的卡片（一行三張），被退回的換成提示的顏色；
// 退回理由在修改活動的表單最上面
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
    <a class="publish-card" href="#/merchant/new">
      <span class="publish-plus" aria-hidden="true">＋</span>
      <span class="publish-text"><b>上架新活動</b><span>填寫活動資料送出審核，也可以從過去的活動帶入資料</span></span>
      <span class="publish-arrow" aria-hidden="true">→</span>
    </a>
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

// 和找活動的活動卡片一樣（圖片、類別、票價、日期、場館），左上角加審核狀態，下方加收藏數與操作按鈕
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
        ${e.EventStatus === "已下架" ? "" : `<a class="btn m-edit" href="#/merchant/edit/${e.EventID}">修改</a>`}
      </div>
    </div>
  </article>`;
}

function discountRow(opts, d = {}) {
  return `<div class="discount-row" data-discount>
    <label class="field"><span>優惠類型</span><select class="input" name="d_type">${opts.discount_types.map((t) =>
      `<option value="${t.DiscountTypeID}" ${t.DiscountTypeID === d.DiscountType_FK ? "selected" : ""}>${esc(t.DiscountTypeName)}</option>`).join("")}</select></label>
    <label class="field"><span>優惠價</span><input class="input" name="d_price" type="number" min="0" required value="${d.DiscountPrice ?? ""}"></label>
    <label class="field wide"><span>說明</span><input class="input" name="d_desc" maxlength="100" placeholder="例如：憑學生證購票" value="${esc(d.DiscountDescription ?? "")}"></label>
    <label class="field"><span>開始日期（可空白）</span><input class="input" name="d_start" type="date" value="${isoDay(d.DiscountStartDate)}"></label>
    <label class="field"><span>截止日期（早鳥必填）</span><input class="input" name="d_end" type="date" value="${isoDay(d.DiscountEndDate)}"></label>
    <button type="button" class="btn-text" data-remove aria-label="刪除這筆優惠">刪除</button>
  </div>`;
}

// id：修改這場活動；沒有 id 是上架新活動，可以從自己過去的活動帶入日期以外的資料
async function viewEventForm(id) {
  const here = routeNow();
  if (!requireRole("商家", here)) return;
  app.innerHTML = '<div class="skeleton" style="min-height: 320px"></div>';
  const [opts, venues, e, mine] = await Promise.all([getOptions(), api("/api/venues"),
    id ? api(`/api/events/${id}`) : null, id ? [] : api("/api/merchant/events").catch(() => [])]);
  if (routeNow() !== here) return;
  const venueOptions = (list, selected) => list.map((v) =>
    `<option value="${v.VenueID}" ${v.VenueID === selected ? "selected" : ""}>${esc(v.CityName)}・${esc(v.VenueName)}</option>`).join("");
  app.innerHTML = `
    <a class="back btn-text" href="#/merchant">← 回商家後台</a>
    <div class="form-head">
      <div class="form-title">
        <h1>${id ? "修改活動" : "上架新活動"}</h1>
        ${id ? `<p class="muted">目前狀態：${statusTag(e.EventStatus)}</p>` : ""}
      </div>
      ${mine.length ? `<div class="copy-from">
        <select class="input" id="copy-from" aria-label="帶入過去活動數據（日期以外的資料會自動填好）">
          <option value="" disabled selected hidden>帶入過去活動數據</option>${mine.map((m) =>
          `<option value="${m.EventID}">${esc(m.EventTitle)}・${fmtDay(m.EventStartDate, true)}</option>`).join("")}</select>
        <button type="button" class="btn-text" id="clear-form">清除全部</button>
      </div>` : ""}
    </div>
    ${id && e?.EventStatus === "已退回" ? `<div class="reject-note"><b>退回理由</b>：${esc(e.EventRejectReason || "未註明理由")}</div>` : ""}
    <form class="card panel form" id="event-form">
      <label class="field"><span>活動名稱</span><input class="input" name="title" required maxlength="100" value="${esc(e?.EventTitle ?? "")}"></label>
      <div class="form-grid">
        <label class="field"><span>類別</span><select class="input" name="category_id" required>${categoryOptions(opts, e?.EventCategory_FK)}</select></label>
        <label class="field"><span>場館</span><select class="input" name="venue_id" id="venue-select" required>
          <option value="">請選擇場館</option>${venueOptions(venues, e?.EventVenue_FK)}</select></label>
        <label class="field"><span>開始日期</span><input class="input" type="date" name="start_date" required value="${isoDay(e?.EventStartDate)}"></label>
        <label class="field"><span>結束日期</span><input class="input" type="date" name="end_date" required value="${isoDay(e?.EventEndDate)}"></label>
        <label class="field"><span>全票價格（免費填 0，未公布留空）</span><input class="input" type="number" min="0" name="price" value="${e?.EventOriginalPrice ?? ""}"></label>
        <label class="field"><span>活動網址</span><input class="input" type="url" name="url" maxlength="255" placeholder="https://" value="${esc(e?.EventURL ?? "")}"></label>
        <label class="field"><span>開賣時間（選填）</span><input class="input" type="datetime-local" name="sale_start" value="${e?.EventSaleStartDate ? e.EventSaleStartDate.slice(0, 16) : ""}"></label>
      </div>
      <div id="venue-overlap" class="venue-overlap" aria-live="polite" hidden></div>
      <details class="venue-new" id="venue-new">
        <summary>找不到場館？新增場館</summary>
        <div class="form-grid">
          <label class="field"><span>場館名稱</span><input class="input" id="v-name" maxlength="50"></label>
          <label class="field"><span>縣市</span><select class="input" id="v-city">${opts.cities.map((c) => `<option value="${c.CityID}">${esc(c.CityName)}</option>`).join("")}</select></label>
          <label class="field wide"><span>完整地址</span><input class="input" id="v-address" maxlength="100" placeholder="例如：臺北市大安區和平東路一段162號"></label>
        </div>
        <button type="button" class="btn" id="v-add">新增場館</button>
      </details>
      <div class="field">
        <span>活動圖片（選填）</span>
        <div class="image-picker">
          <div class="image-preview" id="image-preview" aria-live="polite"></div>
          <div class="image-controls">
            <label class="btn" for="image-file">上傳圖片</label>
            <input type="file" id="image-file" accept="${IMAGE_TYPES.join(",")}" hidden>
            <input class="input" type="url" id="image-link" maxlength="255" placeholder="或貼上圖片網址 https://" aria-label="圖片網址">
            <p class="muted small">JPG、PNG、WebP 或 GIF，5 MB 以內</p>
            <button type="button" class="btn-text" id="image-remove" hidden>移除圖片</button>
          </div>
        </div>
        <input type="hidden" name="image_url" value="${esc(e?.EventImageURL ?? "")}">
      </div>
      <label class="field"><span>活動說明</span><textarea class="input" name="description" rows="5">${esc(e?.EventDescription ?? "")}</textarea></label>
      <div>
        <h2>優惠</h2>
        <p class="muted small">早鳥優惠要填截止日期。</p>
        <div id="discounts">${(e?.Discounts ?? []).map((d) => discountRow(opts, d)).join("")}</div>
        <button type="button" class="btn" id="add-discount">＋ 新增一筆優惠</button>
      </div>
      <div id="similar-warn" hidden></div>
      <p class="error" id="form-error" role="alert"></p>
      <div class="filter-actions"><a class="btn-text" href="#/merchant">取消</a>
        <button class="btn btn-primary">${id ? "儲存並重新送審" : "送出審核"}</button></div>
    </form>`;

  const form = document.getElementById("event-form");
  const box = document.getElementById("discounts");
  document.getElementById("add-discount").addEventListener("click", () => box.insertAdjacentHTML("beforeend", discountRow(opts)));
  box.addEventListener("click", (ev) => ev.target.closest("[data-remove]")?.closest("[data-discount]").remove());

  // 選好場館和日期後，列出同場館、日期重疊的已上架活動，安排日期時避開撞期
  const overlap = document.getElementById("venue-overlap");
  let overlapSeq = 0;
  const showOverlap = async () => {
    const { venue_id, start_date, end_date } = form.elements;
    const seq = ++overlapSeq;
    if (!venue_id.value || !start_date.value || !end_date.value || end_date.value < start_date.value) { overlap.hidden = true; return; }
    const query = new URLSearchParams({ venue_id: venue_id.value, start_date: start_date.value, end_date: end_date.value, event_id: id || 0 });
    const list = await api(`/api/merchant/venue-events?${query}`).catch(() => null);
    if (seq !== overlapSeq || !list) return;
    const venue = esc(venue_id.selectedOptions[0].textContent.split("・").pop());
    overlap.innerHTML = list.length
      ? `<b>這段期間 ${venue} 還有 ${list.length} 場已上架的活動</b>，安排日期時可以參考：
        <ul>${list.map((o) => `<li><a href="#/event/${o.EventID}" target="_blank" rel="noopener">${esc(o.EventTitle)}</a>
          <span class="muted small">${esc(o.CategoryName)}・${fmtRange(o.EventStartDate, o.EventEndDate)}</span></li>`).join("")}</ul>`
      : `✓ 這段期間 ${venue} 沒有其他已上架的活動。`;
    overlap.classList.toggle("has-events", list.length > 0);
    overlap.hidden = false;
  };
  ["venue_id", "start_date", "end_date"].forEach((name) => form.elements[name].addEventListener("change", showOverlap));
  showOverlap();

  // 活動圖片：上傳的檔案存在伺服器（uploads/…），或直接用外部圖片網址；表單只送出 image_url
  const preview = document.getElementById("image-preview");
  const link = document.getElementById("image-link");
  const setImage = (url) => {
    form.elements.image_url.value = url || "";
    link.value = url && !url.startsWith("uploads/") ? url : "";
    document.getElementById("image-remove").hidden = !url;
    preview.classList.remove("is-error");
    preview.innerHTML = url ? `<img src="${esc(url)}" alt="活動圖片預覽" referrerpolicy="no-referrer">`
      : '<span class="muted small">還沒有圖片</span>';
    preview.querySelector("img")?.addEventListener("error", () => {
      preview.classList.add("is-error");
      preview.innerHTML = '<span class="small">圖片無法顯示，請確認網址或重新上傳</span>';
    });
  };
  const upload = async (file) => {
    if (!file) return;
    preview.innerHTML = '<span class="muted small">上傳中…</span>';
    try {
      setImage(await uploadImage(file));
      toast("已上傳圖片");
    } catch (err) {
      setImage(form.elements.image_url.value);
      toast(err.message);
    }
  };
  setImage(form.elements.image_url.value);
  document.getElementById("image-file").addEventListener("change", (ev) => { upload(ev.target.files[0]); ev.target.value = ""; });
  link.addEventListener("change", () => setImage(link.value.trim()));
  document.getElementById("image-remove").addEventListener("click", () => setImage(""));
  preview.addEventListener("dragover", (ev) => { ev.preventDefault(); preview.classList.add("is-drop"); });
  preview.addEventListener("dragleave", () => preview.classList.remove("is-drop"));
  preview.addEventListener("drop", (ev) => { ev.preventDefault(); preview.classList.remove("is-drop"); upload(ev.dataTransfer.files[0]); });

  // 從過去的活動帶入：名稱、類別、場館、票價、網址、圖片、說明、優惠都填好；日期、開賣時間、優惠期間留給商家重填
  document.getElementById("copy-from")?.addEventListener("change", async (ev) => {
    if (!ev.target.value) return;
    try {
      const src = await api(`/api/events/${ev.target.value}`);
      const set = (name, value) => (form.elements[name].value = value ?? "");
      set("title", src.EventTitle); set("category_id", src.EventCategory_FK); set("venue_id", src.EventVenue_FK);
      set("price", src.EventOriginalPrice); set("url", src.EventURL); set("description", src.EventDescription);
      setImage(src.EventImageURL);
      box.innerHTML = src.Discounts.map((d) => discountRow(opts, { ...d, DiscountStartDate: null, DiscountEndDate: null })).join("");
      showOverlap();
      toast(`已帶入「${src.EventTitle}」的資料，請填上日期`);
      form.elements.start_date.focus();
    } catch (err) { toast(err.message); }
  });
  // 清除全部：表單回到空白（帶入的資料、優惠、提醒都清掉）
  document.getElementById("clear-form")?.addEventListener("click", () => {
    form.reset();
    setImage("");
    box.innerHTML = "";
    document.getElementById("copy-from").selectedIndex = 0;
    ["venue-overlap", "similar-warn"].forEach((boxId) => (document.getElementById(boxId).hidden = true));
    document.getElementById("form-error").textContent = "";
    delete form.dataset.similarChecked;
    form.elements.title.focus();
  });

  document.getElementById("v-add").addEventListener("click", async () => {
    const name = document.getElementById("v-name").value.trim();
    const address = document.getElementById("v-address").value.trim();
    if (!name || !address) { toast("請填寫場館名稱與地址"); return; }
    try {
      const { venue_id } = await api("/api/venues", { method: "POST", body: JSON.stringify({ name, address, city_id: Number(document.getElementById("v-city").value) }) });
      document.getElementById("venue-select").innerHTML = '<option value="">請選擇場館</option>' + venueOptions(await api("/api/venues"), venue_id);
      document.getElementById("venue-new").open = false;
      showOverlap();
      toast("已新增場館");
    } catch (err) { toast(err.message); }
  });

  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = Object.fromEntries(new FormData(form));
    const body = {
      title: f.title, category_id: Number(f.category_id), venue_id: Number(f.venue_id),
      start_date: f.start_date, end_date: f.end_date, price: f.price === "" ? null : Number(f.price),
      url: f.url || null, description: f.description || null, sale_start: f.sale_start || null, image_url: f.image_url || null,
      discounts: [...box.querySelectorAll("[data-discount]")].map((row) => {
        const v = (name) => row.querySelector(`[name=${name}]`).value;
        return { discount_type_id: Number(v("d_type")), price: Number(v("d_price")), description: v("d_desc") || null,
                 start_date: v("d_start") || null, end_date: v("d_end") || null };
      }),
    };
    const button = form.querySelector("button.btn-primary");
    button.disabled = true;
    try {
      // 送出前先檢查有沒有相似的活動（避免重複上架）；看過提醒、按「仍要送出審核」就不再擋
      const key = JSON.stringify([body.title, body.venue_id, body.start_date, body.end_date]);
      if (form.dataset.similarChecked !== key) {
        const similar = await api("/api/merchant/events/similar", { method: "POST", body: JSON.stringify({
          title: body.title, venue_id: body.venue_id, start_date: body.start_date, end_date: body.end_date,
          url: body.url, event_id: id ? Number(id) : null }) }).catch(() => []);
        if (similar.length) { showSimilarWarning(form, similar, key); return; }
      }
      await api(id ? `/api/merchant/events/${id}` : "/api/merchant/events", { method: id ? "PUT" : "POST", body: JSON.stringify(body) });
      toast(id ? "已儲存，等待管理員重新審核" : "已送出，等待管理員審核");
      merchant.status = "待審核";
      location.hash = "#/merchant";
    } catch (err) {
      document.getElementById("form-error").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  });
}

// 上傳活動圖片：請求內容直接是圖片檔，回傳存好的路徑（uploads/…）
const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
async function uploadImage(file) {
  if (!IMAGE_TYPES.includes(file.type)) throw new Error("只能上傳 JPG、PNG、WebP 或 GIF 圖片");
  if (file.size > 5 * 1024 * 1024) throw new Error("圖片要在 5 MB 以內");
  const res = await fetch("/api/merchant/images", { method: "POST", body: file,
    headers: { "Content-Type": file.type, Authorization: `Bearer ${token}` } });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `上傳失敗（${res.status}）`);
  return data.url;
}

// 商家送出前的重複提醒：只列已上架的活動和自己的活動
function showSimilarWarning(form, list, key) {
  const box = document.getElementById("similar-warn");
  const likely = list.some((s) => s.Level === "很可能重複");
  box.innerHTML = `<div class="dup-warn ${likely ? "likely" : ""}" role="alert">
    <b>⚠ 系統裡已經有 ${list.length} 場${likely ? "很可能重複" : "相似"}的活動</b>，請確認不是重複上架（重複的活動會被管理員退回）：
    ${similarList(list)}
    <div class="filter-actions">
      <button type="button" class="btn-text" id="similar-back">回去修改</button>
      <button type="button" class="btn" id="similar-go">不是重複，仍要送出審核</button>
    </div></div>`;
  box.hidden = false;
  box.scrollIntoView({ block: "center", behavior: "smooth" });
  document.getElementById("similar-back").addEventListener("click", () => { box.hidden = true; form.elements.title.focus(); });
  document.getElementById("similar-go").addEventListener("click", () => {
    form.dataset.similarChecked = key;
    box.hidden = true;
    form.requestSubmit();
  });
}
