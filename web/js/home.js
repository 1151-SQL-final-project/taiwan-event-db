// 首頁。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 首頁 ----------

// 首頁只放 logo、名稱、介紹，以及「找活動」「登入」兩個按鈕（已登入就不顯示登入）
function viewHome() {
  const here = routeNow();
  app.innerHTML = `
    <section class="home-hero">
      <div class="home-art"><img src="logo.png" alt="探點 logo"></div>
      <h1 class="home-name">探點</h1>
      <p class="eyebrow">SpotGo</p>
      <p class="lead">把全臺灣的展覽、講座、工作坊與表演集中在一起。<br>
        依地區、日期、類型與優惠查詢活動，<br>學生優惠、早鳥票直接標出來，看到喜歡的就收藏起來。</p>
      <div class="home-actions">
        <a class="btn btn-primary" href="#/search">找活動</a>
        ${me ? "" : '<a class="btn" href="#/login">登入／註冊</a>'}
      </div>
    </section>
    <section class="home-section" id="home-student" hidden></section>
    <section class="home-section" id="home-weekend" hidden></section>`;
  loadHomeSections(here);
}

// 首頁的活動區塊：載入失敗或沒有活動時就不顯示，首頁仍然可以用
const HOME_CARDS = 6;
async function loadHomeSections(here) {
  const today = quickRange("today")[0];
  const sunday = new Date(today.getFullYear(), today.getMonth(), today.getDate() + (7 - today.getDay()) % 7);
  const [satOrSun, weekendEnd] = quickRange("weekend");
  const opts = await getOptions().catch(() => null);
  if (routeNow() !== here) return;
  const student = opts?.discount_types.find((t) => t.DiscountTypeName === "學生優惠");
  const show = async (id, title, note, params) => {
    const query = new URLSearchParams({ ...params, sort: "date" });
    const data = await api(`/api/events?${query}&page_size=${HOME_CARDS}`).catch(() => null);
    const box = document.getElementById(id);
    if (routeNow() !== here || !box || !data?.items.length) return;
    box.innerHTML = `
      <div class="strip-head"><h2>${title}</h2><span class="muted small">${note}</span></div>
      <div class="grid">${data.items.map(eventCard).join("")}</div>
      ${data.total > data.items.length ? `<div class="more"><a class="btn" href="#/search" data-see-all>看全部 ${data.total.toLocaleString("zh-TW")} 場</a></div>` : ""}`;
    box.querySelector("[data-see-all]")?.addEventListener("click", () => {
      Object.assign(search, { params: query, items: [], total: 0, page: 1, scrollY: 0, userSearched: false });
    });
    box.hidden = false;
  };
  await Promise.all([
    student && show("home-student", "本週學生優惠", `到 ${fmtDay(ymd(sunday))}`,
      { discount_type_id: student.DiscountTypeID, date_from: ymd(today), date_to: ymd(sunday) }),
    show("home-weekend", "這週末", fmtRange(ymd(satOrSun), ymd(weekendEnd)), { date_from: ymd(satOrSun), date_to: ymd(weekendEnd) }),
  ]);
}
