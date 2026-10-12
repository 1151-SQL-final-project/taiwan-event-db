// 串接測試版網頁的程式。示範怎麼呼叫每一支 API，網頁設計組可以照這裡的寫法接到正式畫面。

const $ = (id) => document.getElementById(id);

// 活動資料來自外部（開放資料），放進畫面前一律跳脫，避免夾帶 HTML
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

const day = (iso) => (iso ? iso.slice(0, 10).replaceAll("-", "/") : "");
const time = (iso) => (iso ? iso.slice(0, 16).replace("T", " ").replaceAll("-", "/") : "");

// 票價規則：0 = 免費、null = 不明，有原始說明就一起顯示
function priceText(price, note) {
  const main = price === null ? "票價未定" : price === 0 ? "免費" : `NT$${price} 起`;
  return note ? `${main}（${note}）` : main;
}

let token = null;
try { token = localStorage.getItem("token"); } catch { /* 無法使用 localStorage 時就只在這一頁有效 */ }

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("；") : data.detail;
    throw new Error(detail || `錯誤 ${res.status}`);
  }
  return data;
}

function setToken(value) {
  token = value;
  try { value ? localStorage.setItem("token", value) : localStorage.removeItem("token"); } catch { /* 略過 */ }
  refreshAccount();
}

// ---------- 1. 串接測試 ----------
$("health-btn").onclick = async () => {
  try { $("health-out").textContent = JSON.stringify(await api("/api/health"), null, 2); }
  catch (err) { $("health-out").textContent = "失敗：" + err.message; }
};

// ---------- 2. 帳號 ----------
async function refreshAccount() {
  if (!token) { $("account-status").textContent = "尚未登入"; return; }
  try {
    const me = await api("/api/me");
    $("account-status").textContent = `已登入：${me.UserName}（${me.UserEmail}），預設縣市：${me.CityName ?? "未設定"}`;
    if (me.UserDefaultCity_FK) $("city").value = me.UserDefaultCity_FK; // 預設查詢縣市
    loadSaves();
  } catch { setToken(null); }
}

$("login-form").onsubmit = async (e) => {
  e.preventDefault();
  const form = new FormData(e.target);
  try {
    const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(Object.fromEntries(form)) });
    $("account-msg").textContent = "";
    setToken(data.token);
  } catch (err) { $("account-msg").textContent = err.message; }
};

$("register-form").onsubmit = async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  body.default_city_id = body.default_city_id ? Number(body.default_city_id) : null;
  try {
    const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify(body) });
    $("account-msg").textContent = "";
    setToken(data.token);
  } catch (err) { $("account-msg").textContent = err.message; }
};

$("logout-btn").onclick = () => { setToken(null); $("saves").innerHTML = ""; };

// ---------- 3. 搜尋 ----------
async function loadOptions() {
  const opts = await api("/api/options");
  const option = (value, text) => `<option value="${esc(value)}">${esc(text)}</option>`;
  $("region").innerHTML += opts.regions.map((r) => option(r, r)).join("");
  const cities = opts.cities.map((c) => option(c.CityID, `${c.CityName}（${c.CityRegion}）`)).join("");
  $("city").innerHTML += cities;
  $("register-city").innerHTML = option("", "不設定") + cities;
  $("category").innerHTML += opts.categories.map((c) => option(c.CategoryID, c.CategoryName)).join("");
  $("discount-types").innerHTML = opts.discount_types
    .map((t) => `<label><input type="checkbox" name="discount_type_id" value="${t.DiscountTypeID}"> ${esc(t.DiscountTypeName)}</label>`)
    .join("");
}

$("search-form").onsubmit = async (e) => {
  e.preventDefault();
  const params = new URLSearchParams();
  for (const [key, value] of new FormData(e.target)) if (value) params.append(key, value);
  try {
    const events = await api("/api/events?" + params);
    $("results").innerHTML = events.length
      ? `<p class="muted">共 ${events.length} 筆</p>` + events.map(eventRow).join("")
      : "<p>沒有符合條件的活動</p>";
  } catch (err) { $("results").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
};

function eventRow(e) {
  const venues = e.Venues.map((v) => `${v.CityName} ${v.VenueName}`).join("、");
  const discount = e.BestDiscountPrice !== null ? `<span class="badge">優惠價 NT$${e.BestDiscountPrice} 起</span>` : "";
  return `<div class="event">
    <a href="#" data-event="${e.EventID}"><b>${esc(e.EventTitle)}</b></a>
    <span class="badge">${esc(e.CategoryName)}</span>${discount}<br>
    <span class="muted">${day(e.EventStartDate)} ～ ${day(e.EventEndDate)}｜${esc(priceText(e.EventOriginalPrice, e.EventPriceNote))}｜${esc(venues)}</span>
  </div>`;
}

document.addEventListener("click", (e) => {
  const link = e.target.closest("[data-event]");
  if (link) { e.preventDefault(); showDetail(link.dataset.event); }
});

async function showDetail(id) {
  const e = await api(`/api/events/${id}`);
  const sessions = e.Sessions.map((s) => `<li>${time(s.SessionStartTime)}${s.SessionEndTime ? " ～ " + time(s.SessionEndTime) : ""}
      ｜${esc(s.CityName)} ${esc(s.VenueName)}（${esc(s.VenueAddress)}）
      <a href="${esc(s.GoogleMapsURL)}" target="_blank" rel="noopener">在 Google 地圖開啟</a></li>`).join("");
  const discounts = e.Discounts.map((d) => `<li>${d.IsValidNow ? "" : "<s>"}${esc(d.DiscountTypeName)}：NT$${d.DiscountPrice}
      ${esc(d.DiscountDescription)}${d.DiscountEndDate ? `（截止 ${day(d.DiscountEndDate)}）` : "（無截止日）"}${d.IsValidNow ? "" : "</s> 已失效"}</li>`).join("");
  $("detail").innerHTML = `
    <h3>${esc(e.EventTitle)} <span class="badge">${esc(e.CategoryName)}</span></h3>
    <p>${day(e.EventStartDate)} ～ ${day(e.EventEndDate)}｜${esc(priceText(e.EventOriginalPrice, e.EventPriceNote))}</p>
    <p>${esc(e.EventDescription)}</p>
    <p><b>場次</b></p><ul>${sessions || "<li>尚無場次資料</li>"}</ul>
    <p><b>優惠</b></p><ul>${discounts || "<li>沒有優惠</li>"}</ul>
    <p>${e.EventURL ? `<a href="${esc(e.EventURL)}" target="_blank" rel="noopener">活動官網</a>｜` : ""}資料來源：${esc(e.EventDataSource)}</p>
    <button id="save-btn">收藏</button> <span id="save-msg"></span>`;
  $("detail-section").hidden = false;
  $("save-btn").onclick = async () => {
    try { await api(`/api/saves/${id}`, { method: "POST" }); $("save-msg").textContent = "已收藏"; loadSaves(); }
    catch (err) { $("save-msg").textContent = err.message; }
  };
  $("detail-section").scrollIntoView({ behavior: "smooth" });
}

// ---------- 4. 我的收藏 ----------
async function loadSaves() {
  if (!token) { $("saves").innerHTML = "<p class='muted'>登入後才能看收藏</p>"; return; }
  try {
    const saves = await api("/api/saves");
    $("saves").innerHTML = saves.length ? saves.map((s) => `<div class="event">
        <a href="#" data-event="${s.EventID}"><b>${esc(s.EventTitle)}</b></a>${s.EventIsActive ? "" : " <span class='badge'>已下架</span>"}
        <span class="muted">${day(s.EventStartDate)} ～ ${day(s.EventEndDate)}｜收藏於 ${time(s.SaveDate)}</span>
        <button data-unsave="${s.EventID}">取消收藏</button></div>`).join("")
      : "<p class='muted'>還沒有收藏</p>";
  } catch (err) { $("saves").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
}

$("saves-btn").onclick = loadSaves;
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-unsave]");
  if (btn) { await api(`/api/saves/${btn.dataset.unsave}`, { method: "DELETE" }); loadSaves(); }
});

loadOptions().then(refreshAccount).catch((err) => { $("results").innerHTML = `<p class="error">${esc(err.message)}</p>`; });
