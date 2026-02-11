(function () {
  var STORAGE_KEY = "vault_token";
  function getToken() {
    return document.getElementById("token")?.value?.trim() || sessionStorage.getItem(STORAGE_KEY) || "";
  }
  function setToken(t) { sessionStorage.setItem(STORAGE_KEY, t); var e = document.getElementById("token"); if (e) e.value = t; }
  function escapeHtml(s) { if (!s) return ""; var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function showPeople(container, data) {
    var list = data.people || [];
    var html = "<div class=\"vault-results-header\"><strong>" + (data.total || list.length) + "</strong> people</div>";
    html += "<div style=\"display:grid; grid-template-columns:repeat(auto-fill, minmax(200px, 1fr)); gap:1rem; margin-top:1rem;\">";
    list.forEach(function (p) {
      html += "<div class=\"vault-card\"><h3 class=\"vault-card-title\">" + escapeHtml(p.name) + "</h3>";
      if (p.role_or_title) html += "<p class=\"vault-card-meta\">" + escapeHtml(p.role_or_title) + "</p>";
      html += "</div>";
    });
    html += "</div>";
    if (list.length === 0) html += "<p class=\"vault-empty\">No people in the directory yet.</p>";
    container.innerHTML = html;
  }
  function showError(container, msg) { container.innerHTML = "<div class=\"vault-err\">" + escapeHtml(msg) + "</div>"; }
  window.VaultPeople = {
    load: function () {
      var container = document.getElementById("vault-people");
      var token = getToken();
      if (!token) { showError(container, "Paste a Supabase access token above."); return; }
      setToken(token);
      container.innerHTML = "<div class=\"vault-loading\">Loading…</div>";
      var apiBase = window.VaultConfig?.apiBase || "";
      fetch(apiBase + "/people?limit=200", { method: "GET", headers: { Authorization: "Bearer " + token } })
        .then(function (r) { return r.json().then(function (j) {
          if (r.status === 401) showError(container, "Invalid or expired token.");
          else if (!r.ok) showError(container, j.detail || "Request failed");
          else showPeople(container, j);
        }); })
        .catch(function (err) { showError(container, err.message || "Network error"); });
    },
  };
  document.addEventListener("DOMContentLoaded", function () {
    var s = sessionStorage.getItem(STORAGE_KEY), el = document.getElementById("token");
    if (s && el) el.value = s;
  });
})();
