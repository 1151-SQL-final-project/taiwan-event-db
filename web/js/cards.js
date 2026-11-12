// 活動卡片、類別插圖、即將開賣與早鳥即將截止的活動列（首頁、找活動、收藏都會用到）。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// 沒有活動圖片（或圖片載入失敗）時顯示類別插圖：像小海報一樣滿版的幾何圖形，顏色取自 logo 的深藍、赭紅、米白。
// 每個類別有自己的圖形和固定的一種配色，再依活動編號左右翻轉，同類別的卡片排在一起才不會全部一樣。
// [底色, 主色, 輔色, 點綴]
const ART_NAVY = ["#203a55", "#f2eadc", "#c9744d", "#7f9ab3"];
const ART_RUST = ["#a9583a", "#f7efe2", "#203a55", "#e7b98f"];
const ART_SAND = ["#eadfcd", "#203a55", "#b8643f", "#8ea5ba"];
const ART_BLUE = ["#55748f", "#f4ecdf", "#203a55", "#e9b48d"];
const ART_SCENES = {
  // 五線譜與音符
  "音樂表演": { colors: ART_NAVY, noFlip: true, draw: ([, a, b, c]) => `
    <g fill="none" stroke="${c}" stroke-width="2">${[0, 1, 2, 3, 4].map((i) => `<path d="M-10 ${70 + i * 15}C70 ${30 + i * 15} 150 ${125 + i * 15} 330 ${50 + i * 15}"/>`).join("")}</g>
    <g fill="${a}"><ellipse cx="100" cy="122" rx="17" ry="13" transform="rotate(-20 100 122)"/><path d="M113 118h5V42h-5z"/>
      <ellipse cx="166" cy="110" rx="17" ry="13" transform="rotate(-20 166 110)"/><path d="M179 106h5V30h-5z"/><path d="M113 42l71-12v15l-71 12z"/></g>
    <circle cx="256" cy="52" r="24" fill="${b}"/><circle cx="46" cy="38" r="7" fill="${b}"/>` },
  // 交疊的展示框
  "展覽": { colors: ART_SAND, draw: ([, a, b, c]) => `
    <g fill="none" stroke="${a}" stroke-width="5"><rect x="34" y="52" width="72" height="88"/><rect x="124" y="36" width="78" height="104"/><rect x="220" y="66" width="66" height="74"/></g>
    <circle cx="70" cy="96" r="20" fill="${b}"/><path d="M136 128 163 66l27 62z" fill="${c}"/><rect x="238" y="86" width="30" height="34" fill="${b}"/>
    <path d="M18 160h284" stroke="${a}" stroke-width="3"/>` },
  // 布幕與聚光燈
  "戲劇": { colors: ART_RUST, draw: ([, a, b, c]) => `
    <path d="M160 -10 62 180h196z" fill="${c}" opacity=".55"/>
    <ellipse cx="160" cy="166" rx="84" ry="13" fill="${a}"/>
    <path d="M-5-5H96C90 62 62 118 18 180H-5z" fill="${b}"/><path d="M325-5H224c6 67 34 123 78 185h23z" fill="${b}"/>
    <path d="M-5-5h330v24c-22 22-46 22-66 0-20 22-46 22-66 0-20 22-46 22-66 0-20 22-46 22-66 0-20 22-44 22-66 0z" fill="${a}"/>` },
  // 講台、麥克風和投影幕
  "講座": { colors: ART_BLUE, noFlip: true, draw: ([, a, b, c]) => `
    <rect x="166" y="18" width="140" height="6" rx="3" fill="${c}"/><rect x="174" y="24" width="124" height="84" fill="${a}"/>
    <path d="M236 108v44M214 168l22-16 22 16" fill="none" stroke="${c}" stroke-width="4" stroke-linecap="round"/>
    <path d="M192 92l24-24 22 14 38-38" fill="none" stroke="${b}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
    <path d="M100 86 116 52" stroke="${c}" stroke-width="4" stroke-linecap="round"/>
    <ellipse cx="119" cy="45" rx="8" ry="11" transform="rotate(25 119 45)" fill="${b}"/>
    <path d="M34 98h104l-10 82H44z" fill="${a}"/><rect x="26" y="86" width="120" height="14" rx="3" fill="${b}"/>
    <circle cx="86" cy="134" r="12" fill="none" stroke="${b}" stroke-width="4"/>` },
  // 舉手旋轉的舞者與緞帶
  "舞蹈": { colors: ART_NAVY, draw: ([, a, b, c]) => `
    <path d="M-10 142C60 66 112 74 160 104s110 34 170-34" fill="none" stroke="${b}" stroke-width="20" stroke-linecap="round"/>
    <path d="M-10 58c70-22 112 14 166 40s110 30 174 4" fill="none" stroke="${c}" stroke-width="3"/>
    <circle cx="165" cy="44" r="13" fill="${a}"/>
    <path d="M165 60 124 24M165 60l36-38" stroke="${a}" stroke-width="8" stroke-linecap="round"/>
    <path d="M152 58h26l6 42 34 58c-40 14-90 14-136 0l34-58z" fill="${a}"/>
    <path d="M152 168v14M178 168v14" stroke="${a}" stroke-width="8" stroke-linecap="round"/>` },
  // 動手做的工具：鐵鎚、畫筆和作品
  "工作坊": { colors: ART_SAND, draw: ([, a, b, c]) => `
    <path d="M-5 150h330v35H-5z" fill="${c}"/>
    <g transform="rotate(38 160 92)"><rect x="153" y="46" width="14" height="108" rx="5" fill="${a}"/><rect x="124" y="22" width="72" height="34" rx="5" fill="${b}"/></g>
    <g transform="rotate(-38 160 92)"><rect x="154" y="62" width="12" height="94" rx="5" fill="${a}"/><rect x="150" y="48" width="20" height="18" fill="${c}"/><path d="M150 48c0-16 6-26 10-34 4 8 10 18 10 34z" fill="${b}"/></g>
    <circle cx="44" cy="58" r="13" fill="${b}"/><rect x="262" y="42" width="26" height="26" fill="${a}"/>` },
  // 原子軌道
  "科普展覽": { colors: ART_BLUE, draw: ([, a, b, c]) => `
    <g fill="none" stroke="${a}" stroke-width="3"><ellipse cx="160" cy="90" rx="118" ry="38"/><ellipse cx="160" cy="90" rx="118" ry="38" transform="rotate(60 160 90)"/><ellipse cx="160" cy="90" rx="118" ry="38" transform="rotate(120 160 90)"/></g>
    <circle cx="160" cy="90" r="20" fill="${b}"/><circle cx="278" cy="90" r="9" fill="${b}"/>
    <circle cx="101" cy="30" r="8" fill="${c}"/><circle cx="101" cy="150" r="8" fill="${a}"/>
    <g fill="${c}"><circle cx="32" cy="34" r="3"/><circle cx="292" cy="30" r="3"/><circle cx="36" cy="150" r="4"/><circle cx="286" cy="154" r="3"/></g>` },
  // 打開的書和學士帽：一段時間的研習課程
  "研習營隊": { colors: ART_RUST, draw: ([, a, b, c]) => `
    <path d="M160 96c-30-16-70-18-110-10v84c40-8 80-6 110 10z" fill="${a}"/>
    <path d="M160 96c30-16 70-18 110-10v84c-40-8-80-6-110 10z" fill="${a}"/>
    <path d="M160 96v84" stroke="${c}" stroke-width="3"/>
    <g fill="none" stroke="${c}" stroke-width="3" stroke-linecap="round">${[112, 128, 144].map((y) => `<path d="M68 ${y}c26-5 52-3 76 5M176 ${y + 5}c24-8 50-10 76-5"/>`).join("")}</g>
    <path d="M160 8l66 22-66 22-66-22z" fill="${b}"/><path d="M128 40v20c18 12 46 12 64 0V40l-32 12z" fill="${b}"/>
    <path d="M226 30v30" stroke="${b}" stroke-width="3"/><circle cx="226" cy="64" r="6" fill="${c}"/>` },
  // 市集的條紋遮陽棚
  "市集": { colors: ART_RUST, draw: ([, a, b, c]) => `
    ${[0, 1, 2, 3, 4, 5, 6].map((i) => `<path d="M${i * 48 - 8} -5h48v78a24 24 0 0 1-48 0z" fill="${i % 2 ? b : a}"/>`).join("")}
    <g fill="${c}"><circle cx="118" cy="146" r="16"/><circle cx="160" cy="150" r="13"/><circle cx="202" cy="146" r="16"/></g>
    <path d="M96 170h128" stroke="${a}" stroke-width="5" stroke-linecap="round"/>` },
  // 賽道與獎盃
  "體育賽事": { colors: ART_BLUE, draw: ([, a, b, c]) => `
    <g fill="none" stroke="${c}" stroke-width="4">${[128, 156, 184, 212].map((r) => `<circle cx="160" cy="214" r="${r}"/>`).join("")}</g>
    <path d="M128 66H100c0 26 12 40 34 42M192 66h28c0 26-12 40-34 42" fill="none" stroke="${a}" stroke-width="6"/>
    <path d="M124 52h72v42a36 36 0 0 1-72 0z" fill="${a}"/><path d="M153 128h14v24h-14z" fill="${a}"/><rect x="128" y="150" width="64" height="14" fill="${b}"/>` },
};
// 其他類別：logo 的交疊圓
const ART_DEFAULT = { colors: ART_SAND, draw: ([, a, b, c]) => `
  <g fill="none" stroke="${a}" stroke-width="3"><circle cx="130" cy="72" r="46"/><circle cx="190" cy="72" r="46"/><circle cx="160" cy="118" r="46"/></g>
  <circle cx="160" cy="88" r="11" fill="${b}"/><circle cx="264" cy="40" r="7" fill="${c}"/><circle cx="50" cy="144" r="7" fill="${b}"/>` };
function categoryArt(category, seed = 0) {
  const scene = ART_SCENES[category] ?? ART_DEFAULT;
  // 編號打散後決定要不要左右翻轉，相鄰的活動才不會都同一個樣子
  const n = Math.imul(Math.abs(Number(seed)) || 0, 2654435761) >>> 8;
  const colors = scene.colors;
  const flip = !scene.noFlip && (n >>> 7) % 2 ? ' transform="translate(320 0) scale(-1 1)"' : "";
  return `<svg class="thumb-art" viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><rect x="-5" y="-5" width="330" height="190" fill="${colors[0]}"/><g${flip}>${scene.draw(colors)}</g></svg>`;
}
function eventThumb(e) {
  if (!e.EventImageURL) return `<div class="event-thumb art">${categoryArt(e.CategoryName, e.EventID)}</div>`;
  return `<div class="event-thumb"><img src="${esc(e.EventImageURL)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer"
    data-category="${esc(e.CategoryName)}" data-seed="${esc(e.EventID)}"></div>`;
}
// 外部圖片可能失效：卡片換成類別插圖，活動頁的大圖直接拿掉（error 事件不會冒泡，要在捕捉階段接）
document.addEventListener("error", (ev) => {
  const img = ev.target;
  if (img.tagName !== "IMG") return;
  if (img.dataset.category !== undefined) {
    const box = img.parentElement;
    box.classList.add("art");
    box.innerHTML = categoryArt(img.dataset.category, img.dataset.seed);
  } else if (img.dataset.cover !== undefined) img.parentElement.remove();
}, true);

function eventCard(e) {
  const p = priceView(e.EventOriginalPrice, e.BestDiscountPrice, e.EventURL);
  return `<a class="card event-card" href="#/event/${e.EventID}">
    ${eventThumb(e)}
    <div class="event-body">
      <div><span class="tag">${esc(e.CategoryName)}</span> ${p.tag ?? ""} ${saleTag(e.EventSaleStartDate)}</div>
      <h3>${esc(e.EventTitle)}</h3>
      <div class="event-meta">
        <div>📅 ${fmtRange(e.EventStartDate, e.EventEndDate)}</div>
        <div>📍 ${esc(`${e.CityName}・${e.VenueName}`)}</div>
      </div>
      <div class="price-row">
        <span class="price ${p.muted ? "muted" : ""}">${esc(p.main)}</span>
        ${p.old ? `<span class="price-old">${esc(p.old)}</span>` : ""}
      </div>
    </div>
  </a>`;
}

// 小區塊（即將開賣、早鳥即將截止）：先顯示前 4 筆，其他的按「顯示更多」才出現
const STRIP_FIRST = 4;
function renderStrip(id, title, note, list, item) {
  const box = document.getElementById(id);
  if (!box || !list.length) return;
  const rest = list.length - STRIP_FIRST;
  box.innerHTML = `
    <div class="strip-head"><h2>${title}</h2><span class="muted small">${note}</span></div>
    <div class="strip-list">${list.map((x, i) => item(x).replace("<a ", `<a ${i >= STRIP_FIRST ? "hidden " : ""}`)).join("")}</div>
    ${rest > 0 ? `<button type="button" class="btn-text strip-more" aria-expanded="false">顯示更多（還有 ${rest} 場）</button>` : ""}`;
  box.querySelector(".strip-more")?.addEventListener("click", (ev) => {
    const open = ev.target.getAttribute("aria-expanded") !== "true";
    box.querySelectorAll(".strip-item").forEach((a, i) => (a.hidden = !open && i >= STRIP_FIRST));
    ev.target.setAttribute("aria-expanded", open);
    ev.target.textContent = open ? "收合" : `顯示更多（還有 ${rest} 場）`;
  });
  box.hidden = false;
}

// 即將開賣：熱門演唱會一開賣就賣完，提早告訴使用者開賣時間
async function loadSaleSoon() {
  const list = await api("/api/sales/upcoming?days=14").catch(() => []);
  renderStrip("sale-soon", "🎫 即將開賣", `14 天內開賣・共 ${list.length} 場`, list, (e) => `
      <a class="card strip-item" href="#/event/${e.EventID}">
        <span class="tag tag-sale">${e.DaysLeft === 0 ? "今天" : `${e.DaysLeft} 天後`} ${esc(fmtTime(e.EventSaleStartDate).split(" ")[1])} 開賣</span>
        <b class="strip-title">${esc(e.EventTitle)}</b>
        <span class="muted small">${fmtRange(e.EventStartDate, e.EventEndDate)}・${esc(e.CityName)}</span>
      </a>`);
}

async function loadEarlyBird() {
  const list = await api("/api/discounts/early-bird?days=14").catch(() => []);
  renderStrip("early-bird", "⏰ 早鳥即將截止", `14 天內截止・共 ${list.length} 場`, list, (d) => `
      <a class="card strip-item" href="#/event/${d.EventID}">
        <span class="tag tag-warn">${d.DaysLeft === 0 ? "今天截止" : `剩 ${d.DaysLeft} 天`}</span>
        <b class="strip-title">${esc(d.EventTitle)}</b>
        <span><span class="price">${money(d.DiscountPrice)}</span>
          ${d.EventOriginalPrice ? `<span class="price-old">${money(d.EventOriginalPrice)}</span>` : ""}</span>
      </a>`);
}
