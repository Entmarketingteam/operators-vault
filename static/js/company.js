(function () {
  var STORAGE_KEY = "vault_token";
  function getToken() { return document.getElementById("token")?.value?.trim() || sessionStorage.getItem(STORAGE_KEY) || ""; }
  function setToken(t) { sessionStorage.setItem(STORAGE_KEY, t); var e = document.getElementById("token"); if (e) e.value = t; }
  function escapeHtml(s) { if (!s) return ""; var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function formatDuration(sec) { if (sec == null) return ""; var m = Math.floor(sec / 60); var s = Math.round(sec % 60); return m + ":" + (s < 10 ? "0" : "") + s; }
  function titleForDisplay(raw, podcast) {
    if (!raw || (podcast || "").toLowerCase() !== "titans") return raw;
    var t = raw.replace(/^\s*Operators?\s+Titans\s*[-:\s]*/i, "").trim(); return t || raw;
  }
  function renderInsight(h) {
    var title = titleForDisplay(h.title || "(no title)", h.podcast);
    var podcastLabel = (h.podcast || "").replace(/_/g, " ");
    var watchUrl = "https://www.youtube.com/watch?v=" + (h.video_id || "") + (h.start_time_sec != null ? "&t=" + Math.round(h.start_time_sec) : "");
    var watchLabel = h.start_time_sec != null ? "Watch @ " + formatDuration(h.start_time_sec) : "Watch";
    return "<div class=\"vault-card\"><div class=\"vault-card-header\"><h3 class=\"vault-card-title\">" + escapeHtml(title) + "</h3><span class=\"vault-pill\">" + escapeHtml(h.category || "") + "</span></div><p class=\"vault-card-meta\">" + escapeHtml(podcastLabel) + " · <a href=\"" + escapeHtml(watchUrl) + "\" target=\"_blank\" rel=\"noopener\">" + escapeHtml(watchLabel) + "</a></p>" + (h.description ? "<p class=\"vault-card-snippet\">" + escapeHtml(h.description).substring(0, 300) + "</p>" : "") + "<a href=\"" + escapeHtml(watchUrl) + "\" target=\"_blank\" rel=\"noopener\" class=\"vault-watch-btn\">▶ " + escapeHtml(watchLabel) + "</a></div>";
  }
  function renderEpisode(ep) {
    var title = titleForDisplay(ep.title || "(no title)", ep.podcast);
    var podcastLabel = (ep.podcast || "").replace(/_/g, " ");
    var watchUrl = "https://www.youtube.com/watch?v=" + (ep.video_id || "");
    return "<div class=\"vault-card\"><h3 class=\"vault-card-title\">" + escapeHtml(title) + "</h3><p class=\"vault-card-meta\">" + escapeHtml(podcastLabel) + (ep.published_at ? " · " + new Date(ep.published_at).toLocaleDateString() : "") + "</p><a href=\"" + escapeHtml(watchUrl) + "\" target=\"_blank\" rel=\"noopener\" class=\"vault-watch-btn\">▶ Watch</a></div>";
  }
  function showCompany(container, data) {
    document.getElementById("company-name").textContent = data.name || "Company";
    document.getElementById("company-type").textContent = (data.type || "other").charAt(0).toUpperCase() + (data.type || "other").slice(1);
    document.getElementById("company-desc").textContent = data.description || "";
    var html = "";
    if (data.insights && data.insights.length) {
      html += "<h2 style=\"margin-top:2rem;\">Insights (" + data.insights.length + ")</h2><div class=\"vault-results-list\">";
      data.insights.forEach(function (h) { html += renderInsight(h); });
      html += "</div>";
    }
    if (data.episodes && data.episodes.length) {
      html += "<h2 style=\"margin-top:2rem;\">Episodes (" + data.episodes.length + ")</h2><div class=\"vault-results-list\" style=\"display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:1rem;\">";
      data.episodes.forEach(function (ep) { html += renderEpisode(ep); });
      html += "</div>";
    }
    if (!html) html = "<p class=\"vault-empty\">No insights or episodes yet.</p>";
    container.innerHTML = html;
  }
  function showError(container, msg) { container.innerHTML = "<div class=\"vault-err\">" + escapeHtml(msg) + "</div>"; }
  function load() {
    var container = document.getElementById("vault-company-content");
    var token = getToken();
    if (!token) { showError(container, "Paste a Supabase access token above."); return; }
    setToken(token);
    var slug = window.location.pathname.split("/").pop();
    if (!slug || slug === "company-ui") { showError(container, "Invalid company slug."); return; }
    container.innerHTML = "<div class=\"vault-loading\">Loading…</div>";
    var apiBase = window.VaultConfig?.apiBase || "";
    fetch(apiBase + "/company/" + encodeURIComponent(slug), { method: "GET", headers: { Authorization: "Bearer " + token } })
      .then(function (r) { return r.json().then(function (j) {
        if (r.status === 401) showError(container, "Invalid or expired token.");
        else if (r.status === 404) showError(container, "Company not found.");
        else if (!r.ok) showError(container, j.detail || "Request failed");
        else showCompany(container, j);
      }); })
      .catch(function (err) { showError(container, err.message || "Network error"); });
  }
  window.VaultCompany = { load: load };
  document.addEventListener("DOMContentLoaded", function () {
    var s = sessionStorage.getItem(STORAGE_KEY), el = document.getElementById("token");
    if (s && el) el.value = s;
    load();
  });
})();
