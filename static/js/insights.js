(function () {
  var STORAGE_KEY = "vault_token";
  var TYPE_TO_CATEGORY = {
    quote: "Quotes",
    frameworks: "Frameworks and exercises",
    business_ideas: "Business ideas",
    opinions: "Points of view",
    stories: "Stories and anecdotes",
    product: "Products",
  };
  var TYPE_LABELS = {
    quote: "Quotes",
    frameworks: "Frameworks",
    business_ideas: "Business ideas",
    opinions: "Points of view",
    stories: "Stories",
    product: "Products",
  };
  function getToken() {
    return document.getElementById("token")?.value?.trim() || sessionStorage.getItem(STORAGE_KEY) || "";
  }
  function setToken(t) { sessionStorage.setItem(STORAGE_KEY, t); var e = document.getElementById("token"); if (e) e.value = t; }
  function escapeHtml(s) { if (!s) return ""; var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function formatDuration(sec) {
    if (sec == null) return ""; var m = Math.floor(sec / 60); var s = Math.round(sec % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }
  function titleForDisplay(raw, podcast) {
    if (!raw || (podcast || "").toLowerCase() !== "titans") return raw;
    var t = raw.replace(/^\s*Operators?\s+Titans\s*[-:\s]*/i, "").trim(); return t || raw;
  }
  function renderHit(h) {
    var title = titleForDisplay(h.headline_title || h.title || "(no title)", h.podcast);
    var snippet = h.headline_description || h.description || "";
    var podcastLabel = (h.podcast || "").replace(/_/g, " ");
    var watchUrl = "https://www.youtube.com/watch?v=" + (h.video_id || "") + (h.start_time_sec != null ? "&t=" + Math.round(h.start_time_sec) : "");
    var watchLabel = h.start_time_sec != null ? "Watch @ " + formatDuration(h.start_time_sec) : "Watch";
    return "<div class=\"vault-card\">" +
      "<div class=\"vault-card-header\"><h3 class=\"vault-card-title\">" + escapeHtml(title) + "</h3>" +
      "<span class=\"vault-pill\">" + escapeHtml(h.category || "") + "</span></div>" +
      "<p class=\"vault-card-meta\">" + escapeHtml(podcastLabel) + " · <a href=\"" + escapeHtml(watchUrl) + "\" target=\"_blank\" rel=\"noopener\">" + escapeHtml(watchLabel) + "</a></p>" +
      (snippet ? "<p class=\"vault-card-snippet\">" + escapeHtml(snippet).substring(0, 300) + (snippet.length > 300 ? "…" : "") + "</p>" : "") +
      "<a href=\"" + escapeHtml(watchUrl) + "\" target=\"_blank\" rel=\"noopener\" class=\"vault-watch-btn\">▶ " + escapeHtml(watchLabel) + "</a></div>";
  }
  function showInsights(container, data) {
    var hits = data.hits || [];
    var total = data.total != null ? data.total : hits.length;
    var html = "<div class=\"vault-results-header\"><strong>" + total + "</strong> result" + (total === 1 ? "" : "s") + "</div><div class=\"vault-results-list\">";
    hits.forEach(function (h) { html += renderHit(h); });
    html += "</div>";
    if (hits.length === 0) html += "<p class=\"vault-empty\">No insights in this category yet.</p>";
    container.innerHTML = html;
  }
  function showError(container, msg) { container.innerHTML = "<div class=\"vault-err\">" + escapeHtml(msg) + "</div>"; }
  window.VaultInsights = {
    load: function () {
      var container = document.getElementById("vault-insights");
      var token = getToken();
      if (!token) { showError(container, "Paste a Supabase access token above."); return; }
      setToken(token);
      var typeEl = document.getElementById("insights-type");
      var panzerEl = document.getElementById("insights-panzerism");
      var type = (typeEl && typeEl.value) || "quote";
      var isPanzer = panzerEl && panzerEl.checked;
      var category = TYPE_TO_CATEGORY[type] || "Quotes";
      var label = TYPE_LABELS[type] || type;
      if (isPanzer && type === "quote") label = "Panzerisms";
      document.getElementById("insights-title").textContent = label;
      document.getElementById("insights-subtitle").textContent = "Insights from the vault.";
      container.innerHTML = "<div class=\"vault-loading\">Loading…</div>";
      var apiBase = window.VaultConfig?.apiBase || "";
      var url = apiBase + "/insights?category=" + encodeURIComponent(category) + "&limit=50";
      if (isPanzer) {
        // Use search with is_panzerism filter instead
        url = apiBase + "/search?q=" + encodeURIComponent(category) + "&category=" + encodeURIComponent(category) + "&is_panzerism=true&limit=50";
        fetch(url, { method: "GET", headers: { Authorization: "Bearer " + token } })
          .then(function (r) { return r.json().then(function (j) {
            if (r.status === 401) showError(container, "Invalid or expired token.");
            else if (!r.ok) showError(container, j.detail || "Request failed");
            else showInsights(container, j);
          }); })
          .catch(function (err) { showError(container, err.message || "Network error"); });
      } else {
        fetch(url, { method: "GET", headers: { Authorization: "Bearer " + token } })
          .then(function (r) { return r.json().then(function (j) {
            if (r.status === 401) showError(container, "Invalid or expired token.");
            else if (!r.ok) showError(container, j.detail || "Request failed");
            else showInsights(container, j);
          }); })
          .catch(function (err) { showError(container, err.message || "Network error"); });
      }
    },
  };
  document.addEventListener("DOMContentLoaded", function () {
    var params = new URLSearchParams(window.location.search);
    var type = params.get("type") || "quote";
    var el = document.getElementById("insights-type");
    if (el && TYPE_TO_CATEGORY[type]) el.value = type;
    var s = sessionStorage.getItem(STORAGE_KEY), tokenEl = document.getElementById("token");
    if (s && tokenEl) tokenEl.value = s;
  });
})();
