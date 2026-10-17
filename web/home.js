// 首頁的程式：從 API 算出活動數量、各地區活動數，並加上優惠的快速查詢按鈕。
// 入口目前都連到串接測試頁 test.html（網址參數會自動帶進搜尋表單）。

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]);

const REGION_NOTE = { "北部": "基北北桃竹苗宜", "中部": "中彰投雲", "南部": "嘉南高屏", "東部": "花蓮、臺東", "離島": "澎金馬" };
const searchLink = (params) => "test.html?" + new URLSearchParams(params);

async function getJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`錯誤 ${res.status}`);
  return res.json();
}

async function loadHome() {
  const [opts, events] = await Promise.all([getJSON("/api/options"), getJSON("/api/events")]);
  const regionOf = Object.fromEntries(opts.cities.map((c) => [c.CityName, c.CityRegion]));

  const count = (list) => list.length.toLocaleString("zh-TW");
  const nums = [count(events), new Set(events.map((e) => e.CityName)).size.toLocaleString("zh-TW"), count(opts.categories)];
  document.querySelectorAll("#home-stats b").forEach((b, i) => (b.textContent = nums[i]));

  document.getElementById("home-regions").innerHTML = opts.regions.map((r) => `
    <a class="card tile" href="${esc(searchLink({ region: r }))}">
      <b>${esc(r)}</b><span>${esc(REGION_NOTE[r] ?? "")}</span>
      <span>${count(events.filter((e) => regionOf[e.CityName] === r))} 場活動</span>
    </a>`).join("");

  // 優惠類型（學生優惠、早鳥優惠…）的快速查詢
  document.getElementById("home-quick").insertAdjacentHTML("beforeend", opts.discount_types.map((t) =>
    `<a class="pill" href="${esc(searchLink({ discount_type_id: t.DiscountTypeID }))}">有${esc(t.DiscountTypeName)}</a>`).join(""));
}

loadHome().catch((err) => {
  document.getElementById("home-regions").innerHTML = `<p class="error">讀取活動資料失敗：${esc(err.message)}（後端有啟動嗎？）</p>`;
});
