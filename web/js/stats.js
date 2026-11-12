// 數據：統計圖表與滑鼠提示。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 數據 ----------

function barChart(rows, label, value, unit, titleId) {
  const max = Math.max(...rows.map((r) => r[value]), 1);
  return `<div class="bars" role="list" aria-labelledby="${titleId}">${rows.map((r) => `
    <div class="bar-row" role="listitem" tabindex="0" data-tip="${esc(r[label])}：${r[value].toLocaleString("zh-TW")} ${unit}">
      <span class="bar-label">${esc(r[label])}</span>
      <span class="bar-track"><span class="bar" style="flex: 0 0 calc((100% - 4em) * ${(r[value] / max).toFixed(4)})"></span>
        <span class="bar-value">${r[value].toLocaleString("zh-TW")}</span></span>
    </div>`).join("")}</div>
    <details class="table-view"><summary>以表格檢視</summary>
      <table class="data-table"><thead><tr><th>${{ CityRegion: "地區", CityName: "縣市", EventStatus: "審核狀態" }[label] ?? "類別"}</th><th class="num">${unit}</th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${esc(r[label])}</td><td class="num">${r[value]}</td></tr>`).join("")}</tbody></table>
    </details>`;
}

async function viewStats() {
  app.innerHTML = '<div class="skeleton" style="min-height: 320px"></div>';
  const s = await api("/api/stats");
  if (routeNow() !== "#/stats") return;
  const total = s.categories.reduce((sum, c) => sum + c.EventCount, 0);
  const groups = [...new Set(s.categories.map((c) => c.CategoryGroup))];
  const topSave = Math.max(...s.popular.map((p) => p.SaveCount), 1);
  app.innerHTML = `
    <h1>活動數據</h1>
    <div class="stats-layout">
      <section class="card panel stat-total">
        <div class="muted">目前上架中的活動</div>
        <div class="stat-figure"><span class="hero-number" data-count-to="${total}">${total.toLocaleString("zh-TW")}</span><span class="stat-unit">場</span></div>
      </section>
      <section class="card panel stat-chart">
        <div class="chart-head">
          <h2 id="t-cat">各類別活動數</h2>
          <div class="legend">${groups.map((g, i) => `<span><i class="swatch g${i}"></i>${esc(g)}</span>`).join("")}</div>
        </div>
        ${columnChart(s.categories, groups, "t-cat")}
      </section>
      <section class="card panel stat-rank">
        <h2>熱門收藏排行</h2>
        ${s.popular.length ? `
        <ol class="podium">${s.popular.slice(0, 3).map((p, i) => `
          <li style="--i: ${i}"><a href="#/event/${p.EventID}">
            <span class="podium-no">${i + 1}</span>
            <span class="podium-cat">${esc(p.CategoryName)}</span>
            <span class="podium-title">${esc(p.EventTitle)}</span>
            <span class="podium-count"><b>${p.SaveCount}</b> 人收藏</span>
          </a></li>`).join("")}
        </ol>
        <ol class="top-saves" start="4">${s.popular.slice(3).map((p, i) => `
          <li style="--i: ${i + 3}">
            <span class="top-no">${i + 4}</span>
            <a href="#/event/${p.EventID}">${esc(p.EventTitle)}</a>
            <div class="top-meter"><span style="--w: ${(p.SaveCount / topSave).toFixed(4)}"></span></div>
            <span class="top-count"><b>${p.SaveCount}</b> 人</span>
          </li>`).join("")}
        </ol>` : '<p class="muted">還沒有人收藏</p>'}
      </section>
    </div>`;
  countUp(app.querySelector("[data-count-to]"));
}

// 向上的長條圖：學習類、休閒類用兩種顏色，長條從底部長出來
function columnChart(rows, groups, titleId) {
  const max = Math.max(...rows.map((r) => r.EventCount), 1);
  const step = [10, 20, 25, 50, 100, 200, 250, 500].find((n) => max / n <= 4) ?? 1000;
  const top = step * Math.ceil(max / step);
  const ticks = Array.from({ length: top / step + 1 }, (_, i) => i * step);
  return `<div class="columns" role="list" aria-labelledby="${titleId}" style="--n: ${rows.length}">
    <div class="grid-lines" aria-hidden="true">${ticks.map((v) => `<span style="--y: ${v / top}"><em>${v}</em></span>`).join("")}</div>
    ${rows.map((r, i) => `
      <div class="col" role="listitem" tabindex="0" style="--i: ${i}" data-tip="${esc(r.CategoryName)}（${esc(r.CategoryGroup)}）：${r.EventCount.toLocaleString("zh-TW")} 場">
        <div class="col-bar-area"><div class="col-bar g${groups.indexOf(r.CategoryGroup)}" style="--h: ${(r.EventCount / top).toFixed(4)}">
          <span class="col-value">${r.EventCount.toLocaleString("zh-TW")}</span></div></div>
        <span class="col-label">${esc(r.CategoryName)}</span>
      </div>`).join("")}
  </div>`;
}

// 數字從 0 跳到目標值（使用者設定減少動態效果時直接顯示）
function countUp(el, ms = 1100) {
  const to = Number(el?.dataset.countTo);
  if (!el || !to || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const start = performance.now();
  const tick = (now) => {
    const p = Math.min(1, (now - start) / ms);
    el.textContent = Math.round(to * (1 - (1 - p) ** 3)).toLocaleString("zh-TW");
    if (p < 1 && el.isConnected) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

// 長條圖的滑鼠提示（鍵盤 focus 也會顯示）
const tooltip = document.getElementById("tooltip");
function showTip(target, x, y) {
  tooltip.textContent = target.dataset.tip;
  tooltip.hidden = false;
  const rect = tooltip.getBoundingClientRect();
  tooltip.style.left = `${Math.min(x + 12, window.innerWidth - rect.width - 8)}px`;
  tooltip.style.top = `${Math.max(8, y - rect.height - 10)}px`;
}
document.addEventListener("pointermove", (e) => {
  const t = e.target.closest?.("[data-tip]");
  t ? showTip(t, e.clientX, e.clientY) : (tooltip.hidden = true);
});
document.addEventListener("focusin", (e) => {
  const t = e.target.closest?.("[data-tip]");
  if (t) { const r = t.getBoundingClientRect(); showTip(t, r.left + r.width / 2, r.top); }
});
document.addEventListener("focusout", () => (tooltip.hidden = true));
