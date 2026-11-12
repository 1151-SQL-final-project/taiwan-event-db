// 首頁。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 首頁 ----------

// 首頁只放 logo、名稱、介紹，以及「找活動」「登入」兩個按鈕（已登入就不顯示登入）
function viewHome() {
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
    </section>`;
}
