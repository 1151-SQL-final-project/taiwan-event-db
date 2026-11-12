// 找活動：篩選表單、搜尋結果、分頁。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 找活動 ----------

// requestId：連續改條件時會同時有好幾個搜尋在跑，只採用最後一次的結果
const search = { params: null, items: [], total: 0, page: 1, scrollY: 0, requestId: 0 };

async function viewSearch() {
  const here = routeNow();
  const opts = await getOptions();
  if (routeNow() !== here) return;
  const chip = (name, value, text, type = "radio") =>
    `<label class="chip"><input type="${type}" name="${name}" value="${esc(value)}"><span>${esc(text)}</span></label>`;
  app.innerHTML = `
    <section class="hero">
      <h1>找到課堂之外的好活動</h1>
      <p>展覽、講座、工作坊、表演一次查，學生優惠、早鳥票直接標出來。</p>
    </section>
    <form class="card filters" id="filters">
      <div class="filter-search">
        <label class="field"><span class="sr-only">關鍵字</span><input class="input" name="keyword" type="search" placeholder="搜尋活動或場館，例如：爵士、陶藝"></label>
        <button class="btn btn-primary">搜尋活動</button>
      </div>
      <div class="filter-more" id="filter-more">
        <div class="filter-row">
          <label class="field"><span>縣市</span><select class="input" name="city_id"><option value="">全部縣市</option>
            ${opts.cities.map((c) => `<option value="${c.CityID}">${esc(c.CityName)}</option>`).join("")}</select></label>
          <label class="field"><span>類型</span><select class="input" name="category"><option value="">全部類型</option>
            ${categoryFilterOptions(opts)}</select></label>
        </div>
        <div class="chip-rows">
          <div>
            <div class="chip-label">地區</div>
            <div class="chips">${chip("region", "", "全部")}${opts.regions.map((r) => chip("region", r, r)).join("")}</div>
          </div>
          <div>
            <div class="chip-label">活動狀態</div>
            <div class="chips">${PHASES.map(([value, text]) => chip("phase", value, text)).join("")}</div>
          </div>
        </div>
        <div class="filter-row dates">
          <label class="field"><span>從</span><input class="input" type="date" name="date_from"></label>
          <label class="field"><span>到</span><input class="input" type="date" name="date_to"></label>
          <div class="quick-dates" aria-label="快速選日期">
            <button type="button" class="btn" data-quick="today">今天</button>
            <button type="button" class="btn" data-quick="weekend">這個週末</button>
            <button type="button" class="btn" data-quick="week">未來 7 天</button>
            <button type="button" class="btn" data-quick="month">這個月</button>
          </div>
        </div>
        <div>
          <div class="chip-label">優惠</div>
          <div class="chips">
            ${opts.discount_types.map((t) => chip("discount_type_id", t.DiscountTypeID, t.DiscountTypeName, "checkbox")).join("")}
            ${chip("free_only", "true", "只看免費", "checkbox")}
          </div>
        </div>
        <div class="filter-actions"><button type="reset" class="btn-text">清除條件</button></div>
      </div>
    </form>
    <div id="highlights">
      <section class="strip" id="sale-soon" hidden></section>
      <section class="strip" id="early-bird" hidden></section>
    </div>
    <div class="results-head">
      <h2 id="result-count" aria-live="polite">　</h2>
      <label class="field"><span class="sr-only">排序</span>
        <select class="input" id="sort"><option value="date">依日期（進行中優先）</option><option value="ending">快結束的優先</option><option value="price">價格低到高</option><option value="sale">即將開賣的優先</option></select>
      </label>
    </div>
    <div class="grid" id="results"></div>
    <div class="more"><button class="btn" id="more" hidden>載入更多</button></div>
    <div id="highlights-below"></div>`;

  const form = document.getElementById("filters");
  const initial = search.params ?? new URLSearchParams();
  for (let [key, value] of initial) {
    // 類型下拉選單同時代表 category_id（單一類別）和 category_group（整組，值是「group:學習類」）
    if (key === "category_id") key = "category";
    if (key === "category_group") [key, value] = ["category", `group:${value}`];
    const el = form.elements[key];
    if (!el) continue;
    if (el instanceof RadioNodeList || el.type === "checkbox" || el.type === "radio") {
      form.querySelectorAll(`[name="${key}"]`).forEach((i) => { if (i.value === value) i.checked = true; });
    } else el.value = value;
  }
  const checkAll = () => ["region", "phase"].forEach((name) => {
    if (!form.querySelector(`[name="${name}"]:checked`)) form.querySelector(`[name="${name}"][value=""]`).checked = true;
  });
  checkAll();
  document.getElementById("sort").value = initial.get("sort") || "date";

  form.addEventListener("submit", (e) => { e.preventDefault(); runSearch(form); });
  form.addEventListener("reset", () => setTimeout(() => { checkAll(); runSearch(form, false); }));
  form.querySelectorAll('[name="region"], [name="phase"], [name="discount_type_id"], [name="free_only"], select').forEach((el) =>
    el.addEventListener("change", () => runSearch(form)));
  document.getElementById("sort").addEventListener("change", () => runSearch(form));
  form.querySelectorAll("[data-quick]").forEach((b) => b.addEventListener("click", () => {
    const [from, to] = quickRange(b.dataset.quick);
    form.elements.date_from.value = ymd(from);
    form.elements.date_to.value = ymd(to);
    runSearch(form);
  }));
  document.getElementById("more").addEventListener("click", () => fetchPage(search.page + 1));

  loadSaleSoon();
  loadEarlyBird();
  if (search.params && search.items.length) {
    placeHighlights();
    renderResults();
    requestAnimationFrame(() => window.scrollTo(0, search.scrollY));
  } else {
    runSearch(form, false);
  }
}

// 「即將開賣」「早鳥即將截止」：還沒搜尋時放在搜尋結果上面；使用者搜尋之後移到結果下面，先看到結果
function placeHighlights() {
  const box = document.getElementById("highlights");
  const target = search.userSearched ? document.getElementById("highlights-below") : document.getElementById("results").parentNode;
  if (!box) return;
  if (search.userSearched) target.append(box);
  else target.insertBefore(box, document.querySelector(".results-head"));
  box.classList.toggle("below", !!search.userSearched);
}

// 活動狀態（單選）：即將開始／開賣 = 還沒開始，或還沒開賣；早鳥即將截止 = 14 天內截止，和下方區塊相同
const PHASES = [["", "全部"], ["ongoing", "進行中"], ["upcoming", "即將開始／開賣"], ["early_bird", "早鳥即將截止"]];

// 找活動的類型下拉選單：每組最上面是「整組」（例如全部學習類），下面是該組的各類別
function categoryFilterOptions(opts) {
  return opts.category_groups.map((g) => `<optgroup label="${esc(g)}">
    <option value="group:${esc(g)}">全部${esc(g)}</option>
    ${opts.categories.filter((c) => c.CategoryGroup === g).map((c) => `<option value="${c.CategoryID}">${esc(c.CategoryName)}</option>`).join("")}
  </optgroup>`).join("");
}

// 類別下拉選單依「學習類／休閒類」分組
function categoryOptions(opts, selected = null) {
  return opts.category_groups.map((g) => `<optgroup label="${esc(g)}">${opts.categories.filter((c) => c.CategoryGroup === g)
    .map((c) => `<option value="${c.CategoryID}" ${c.CategoryID === selected ? "selected" : ""}>${esc(c.CategoryName)}</option>`)
    .join("")}</optgroup>`).join("");
}

function quickRange(kind) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const add = (d, n) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);
  if (kind === "today") return [today, today];
  if (kind === "week") return [today, add(today, 6)];
  if (kind === "month") return [today, new Date(today.getFullYear(), today.getMonth() + 1, 0)];
  const saturday = add(today, (6 - today.getDay() + 7) % 7);   // 今天是週日時，算今天這個週末
  return today.getDay() === 0 ? [today, today] : [saturday, add(saturday, 1)];
}

// byUser：使用者按搜尋或改條件（false = 剛打開頁面、清除條件）
function runSearch(form, byUser = true) {
  search.userSearched = byUser;
  placeHighlights();
  const params = new URLSearchParams();
  for (const [key, value] of new FormData(form)) {
    if (!value) continue;
    if (key === "category") params.append(value.startsWith("group:") ? "category_group" : "category_id", value.replace("group:", ""));
    else params.append(key, value);
  }
  params.set("sort", document.getElementById("sort").value);
  search.params = params;
  search.items = [];
  document.getElementById("results").innerHTML = '<div class="skeleton"></div>'.repeat(3);
  fetchPage(1);
}

async function fetchPage(page) {
  const params = new URLSearchParams(search.params);
  params.set("page", page);
  params.set("page_size", 24);
  const more = document.getElementById("more");
  more.disabled = true;
  const requestId = ++search.requestId;
  try {
    const data = await api("/api/events?" + params);
    if (requestId !== search.requestId) return; // 已經有更新的搜尋，這個結果作廢
    if (!document.getElementById("results")) return; // 結果回來前已經離開找活動頁
    search.items = page === 1 ? data.items : search.items.concat(data.items);
    search.total = data.total;
    search.page = page;
    renderResults();
  } catch (err) {
    if (requestId !== search.requestId || !document.getElementById("results")) return;
    document.getElementById("results").innerHTML = `<div class="card empty">${esc(err.message)}</div>`;
  } finally {
    if (requestId === search.requestId) more.disabled = false;
  }
}

function renderResults() {
  document.getElementById("result-count").textContent = `找到 ${search.total.toLocaleString("zh-TW")} 場活動`;
  document.getElementById("results").innerHTML = search.items.length
    ? search.items.map(eventCard).join("")
    : '<div class="card empty" style="grid-column: 1 / -1">沒有符合條件的活動，試著放寬地區或日期。</div>';
  document.getElementById("more").hidden = search.items.length >= search.total;
}
