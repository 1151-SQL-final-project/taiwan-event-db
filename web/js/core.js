// 共用：小工具（日期、票價、跳脫）、登入狀態、呼叫後端 API、選單。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

const app = document.getElementById("app");
const WEEKDAYS = "日一二三四五六";

// ---------- 小工具 ----------

// 活動資料來自外部（開放資料），放進畫面前一律跳脫，避免夾帶 HTML
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const toDate = (iso) => (iso ? new Date(iso.slice(0, 19)) : null);
const ymd = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const money = (n) => `NT$${Number(n).toLocaleString("zh-TW")}`;

function fmtDay(iso, withYear = false) {
  const d = toDate(iso);
  if (!d) return "";
  const year = withYear || d.getFullYear() !== new Date().getFullYear() ? `${d.getFullYear()}/` : "";
  return `${year}${d.getMonth() + 1}/${d.getDate()}（${WEEKDAYS[d.getDay()]}）`;
}
// 開賣時間要到時、分：11/1（六）12:00
function fmtTime(iso) {
  const d = toDate(iso);
  return d ? `${fmtDay(iso)} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` : "";
}
// 還沒開賣：有開賣時間而且還沒到
const notOnSale = (iso) => !!iso && toDate(iso) > new Date();
const saleTag = (iso) => (notOnSale(iso) ? `<span class="tag tag-sale">🎫 ${esc(fmtTime(iso))} 開賣</span>` : "");
function fmtRange(start, end) {
  return ymd(toDate(start)) === ymd(toDate(end)) ? fmtDay(start) : `${fmtDay(start)} – ${fmtDay(end)}`;
}

// 票價規則：0 = 免費、null = 資料沒有票價（不代表要收費或還沒決定，所以請使用者看官網）；有目前有效的優惠且比原價便宜時，顯示優惠價
function priceView(original, best, url) {
  if (original === 0) return { main: "免費", tag: '<span class="tag tag-free">免費</span>' };
  if (best !== null && best !== undefined && (original === null || best < original)) {
    return { main: `${money(best)} 起`, old: original !== null ? money(original) : "", tag: '<span class="tag tag-deal">有優惠</span>' };
  }
  if (original === null) return { main: url ? "票價請見官網" : "票價未公布", muted: true };
  return { main: money(original) };
}

// 審核狀態標籤：待審核、上架中、已退回、已下架
const STATUS_TAG = { "待審核": "tag-warn", "上架中": "tag-free", "已退回": "tag-deal", "已下架": "" };
const statusTag = (s) => `<span class="tag ${STATUS_TAG[s] ?? ""}">${esc(s)}</span>`;
const isoDay = (iso) => (iso ? iso.slice(0, 10) : "");

function toast(message) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => (el.hidden = true), 2600);
}

// ---------- 登入狀態與 API ----------

const store = {
  get(key) { try { return localStorage.getItem(key); } catch { return null; } },
  set(key, value) { try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* 略過 */ } },
};
let token = store.get("token");
let me = null;
let savedIds = new Set();

async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && token) logout(false);
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("；") : data.detail;
    throw Object.assign(new Error(detail || `發生錯誤（${res.status}）`), { status: res.status });
  }
  return data;
}

async function loadMe() {
  if (!token) { me = null; savedIds = new Set(); updateNav(); return; }
  try {
    me = await api("/api/me");
    // 收藏只開放給「使用者」角色
    savedIds = me.UserRole === "使用者" ? new Set((await api("/api/saves")).map((e) => e.EventID)) : new Set();
  } catch { me = null; }
  updateNav();
}

function logout(showToast = true) {
  token = null; me = null; savedIds = new Set();
  store.set("token", null);
  updateNav();
  if (showToast) toast("已登出");
}

function updateNav() {
  document.getElementById("nav-account").textContent = me ? me.UserName : "登入";
  // data-roles：這個選單項目給哪些角色看（guest = 沒登入）
  const role = me ? me.UserRole : "guest";
  document.querySelectorAll("[data-roles]").forEach((a) => (a.hidden = !a.dataset.roles.split(",").includes(role)));
}

let optionsCache = null;
const getOptions = async () => (optionsCache ??= await api("/api/options"));

// 等資料回來時使用者可能已經換頁；這時不要再畫這一頁，否則會蓋掉新的頁面
const routeNow = () => location.hash || "#/";
