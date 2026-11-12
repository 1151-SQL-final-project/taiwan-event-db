// 登入／註冊、帳號頁。
// 所有 js/*.js 是一般的 <script>，依 index.html 的順序載入，彼此共用最上層的變數與函式。

// ---------- 登入／註冊 ----------

// 名稱欄位的說法：商家叫「商家名稱」，其他叫「暱稱」
const nameLabelFor = (role) => (role === "商家" ? "商家名稱" : "暱稱");

// 登入頁的示範帳號（db/demo_events.py 建立的假帳號）
const DEMO_PASSWORD = "test1234";
const DEMO_ACCOUNTS = [["使用者", "student@example.com"], ["商家", "merchant@example.com"], ["管理員", "admin@example.com"]];

async function viewLogin() {
  if (me) {
    const home = { "商家": ["#/merchant", "前往商家後台"], "管理員": ["#/admin", "前往管理員後台"] }[me.UserRole];
    const nameLabel = nameLabelFor(me.UserRole);
    app.innerHTML = `<section class="card auth"><h1>帳號</h1>
      <div><b id="account-name">${esc(me.UserName)}</b> <span class="tag">${esc(me.UserRole)}</span><div class="muted">${esc(me.UserEmail)}</div></div>
      <form class="form" id="name-form">
        <label class="field"><span>${nameLabel}</span>
          <input class="input" name="name" required maxlength="20" value="${esc(me.UserName)}"></label>
        <button class="btn">儲存${nameLabel}</button>
      </form>
      ${home ? `<a class="btn btn-primary" href="${home[0]}">${home[1]}</a>` : ""}
      <button class="btn" id="logout">登出</button></section>`;
    document.getElementById("logout").addEventListener("click", () => { logout(); search.params = null; viewLogin(); });
    document.getElementById("name-form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const button = ev.target.querySelector("button");
      button.disabled = true;
      try {
        me = await api("/api/me", { method: "PUT", body: JSON.stringify({ name: ev.target.elements.name.value }) });
        updateNav();
        document.getElementById("account-name").textContent = me.UserName;
        toast(`已更新${nameLabel}`);
      } catch (err) {
        toast(err.message);
      } finally {
        button.disabled = false;
      }
    });
    return;
  }
  app.innerHTML = `
    <section class="card auth">
      <div class="tabs" role="tablist">
        <button role="tab" aria-selected="true" data-tab="login">登入</button>
        <button role="tab" aria-selected="false" data-tab="register">註冊</button>
      </div>
      <form class="form" id="login-form">
        <label class="field"><span>Email</span><input class="input" name="email" type="email" required autocomplete="email"></label>
        <label class="field"><span>密碼</span><input class="input" name="password" type="password" required autocomplete="current-password"></label>
        <button class="btn btn-primary">登入</button>
      </form>
      <div class="demo-login" id="demo-login">
        <div class="chip-label">示範帳號：點一下直接登入（密碼都是 ${DEMO_PASSWORD}）</div>
        ${DEMO_ACCOUNTS.map(([role, email]) => `<button type="button" class="btn demo-account" data-email="${email}">
          <b>${role}</b><span class="muted small">${email}</span></button>`).join("")}
      </div>
      <form class="form" id="register-form" hidden>
        <div><div class="chip-label">註冊身分</div>
          <div class="chips">
            <label class="chip"><input type="radio" name="role" value="使用者" checked><span>使用者（找活動、收藏）</span></label>
            <label class="chip"><input type="radio" name="role" value="商家"><span>商家（上架活動）</span></label>
          </div></div>
        <label class="field"><span id="name-label">暱稱</span><input class="input" name="name" required maxlength="20"></label>
        <label class="field"><span>Email</span><input class="input" name="email" type="email" required maxlength="50" autocomplete="email"></label>
        <label class="field"><span>密碼（至少 8 碼）</span><input class="input" name="password" type="password" required minlength="8" autocomplete="new-password"></label>
        <button class="btn btn-primary">建立帳號</button>
      </form>
      <p class="error" id="auth-error" role="alert"></p>
    </section>`;

  app.querySelectorAll("[data-tab]").forEach((tab) => tab.addEventListener("click", () => {
    app.querySelectorAll("[data-tab]").forEach((t) => t.setAttribute("aria-selected", t === tab));
    document.getElementById("login-form").hidden = tab.dataset.tab !== "login";
    document.getElementById("register-form").hidden = tab.dataset.tab !== "register";
    document.getElementById("demo-login").hidden = tab.dataset.tab !== "login";
    document.getElementById("auth-error").textContent = "";
  }));
  app.querySelectorAll('#register-form [name="role"]').forEach((r) => r.addEventListener("change", () => {
    document.getElementById("name-label").textContent = nameLabelFor(r.value);
  }));

  // 登入、註冊、示範帳號共用：成功後記住 token，商家、管理員直接到後台（從活動頁來的就回原頁）
  const signIn = async (path, body, button) => {
    button.disabled = true;
    try {
      const data = await api(path, { method: "POST", body: JSON.stringify(body) });
      token = data.token;
      store.set("token", token);
      await loadMe();
      search.params = null; // 換帳號時清掉上一個人的搜尋條件
      toast(`歡迎，${me.UserName}`);
      location.hash = viewLogin.returnTo || { "商家": "#/merchant", "管理員": "#/admin" }[me.UserRole] || "#/";
      viewLogin.returnTo = null;
    } catch (err) {
      document.getElementById("auth-error").textContent = err.message;
    } finally {
      button.disabled = false;
    }
  };
  ["login-form", "register-form"].forEach((id) => document.getElementById(id).addEventListener("submit", (e) => {
    e.preventDefault();
    signIn(id === "login-form" ? "/api/auth/login" : "/api/auth/register",
      Object.fromEntries(new FormData(e.target)), e.target.querySelector("button"));
  }));
  app.querySelectorAll(".demo-account").forEach((b) => b.addEventListener("click", () =>
    signIn("/api/auth/login", { email: b.dataset.email, password: DEMO_PASSWORD }, b)));
}
