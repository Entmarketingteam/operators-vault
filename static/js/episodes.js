/**
 * Episodes catalog: fetch /episodes and render cards. Uses same token as Search.
 */
(function () {
  const STORAGE_KEY = "vault_token";

  function getToken() {
    if (window.VaultAuth && typeof window.VaultAuth.getToken === "function") {
      var t = window.VaultAuth.getToken();
      if (t) return t;
    }
    return document.getElementById("token")?.value?.trim() || sessionStorage.getItem(STORAGE_KEY) || "";
  }

  function setToken(token) {
    sessionStorage.setItem(STORAGE_KEY, token);
    var el = document.getElementById("token");
    if (el) el.value = token;
  }

  function getApiBase() {
    return window.VaultConfig?.apiBase || "";
  }

  function formatDuration(sec) {
    if (sec == null) return "";
    var m = Math.floor(sec / 60);
    var s = Math.round(sec % 60);
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function escapeHtml(s) {
    if (!s) return "";
    var div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function titleForDisplay(rawTitle, podcast) {
    if (!rawTitle || (podcast || "").toLowerCase() !== "titans") return rawTitle;
    var t = rawTitle.replace(/^\s*Operators?\s+Titans\s*[-:\s]*/i, "").trim();
    return t || rawTitle;
  }

  function renderEpisode(ep) {
    var title = titleForDisplay(ep.title || "(no title)", ep.podcast);
    var podcastLabel = (ep.podcast || "").replace(/_/g, " ");
    var watchUrl = "https://www.youtube.com/watch?v=" + (ep.video_id || "");
    var thumb = ep.thumbnail_url
      ? '<img src="' + escapeHtml(ep.thumbnail_url) + '" alt="" style="width:100%; aspect-ratio:16/9; object-fit:cover; border-radius:6px;">'
      : "";
    var views = ep.view_count != null ? (ep.view_count >= 1000 ? (ep.view_count / 1000).toFixed(1) + "K views" : ep.view_count + " views") : "";
    var published = ep.published_at ? new Date(ep.published_at).toLocaleDateString() : "";
    return (
      '<div class="vault-card">' +
      (thumb ? '<div class="vault-card-thumb">' + thumb + "</div>" : "") +
      '<div class="vault-card-header">' +
      '<h3 class="vault-card-title">' + escapeHtml(title) + "</h3>" +
      '<span class="vault-pill">' + escapeHtml(podcastLabel) + "</span>" +
      "</div>" +
      '<p class="vault-card-meta">' +
      (published ? escapeHtml(published) + " · " : "") +
      (ep.duration_seconds != null ? formatDuration(ep.duration_seconds) + " · " : "") +
      (views ? escapeHtml(views) + " · " : "") +
      '<a href="' + escapeHtml(watchUrl) + '" target="_blank" rel="noopener">Watch</a>' +
      "</p>" +
      '<a href="' + escapeHtml(watchUrl) + '" target="_blank" rel="noopener" class="vault-watch-btn">▶ Watch</a>' +
      "</div>"
    );
  }

  function showEpisodes(container, data) {
    var episodes = data.episodes || [];
    var total = data.total != null ? data.total : episodes.length;
    var html =
      '<div class="vault-results-header"><span class="vault-results-count"><strong>' +
      total +
      "</strong> episode" +
      (total === 1 ? "" : "s") +
      "</span></div>";
    if (episodes.length) {
      html += '<div class="vault-results-list" style="display:grid; grid-template-columns:repeat(auto-fill, minmax(280px, 1fr)); gap:1rem;">';
      episodes.forEach(function (ep) {
        html += renderEpisode(ep);
      });
      html += "</div>";
    } else {
      html += '<p class="vault-empty">No episodes in the vault yet. Seed and process from CSV or YouTube.</p>';
    }
    container.innerHTML = html;
  }

  function showError(container, message) {
    container.innerHTML = '<div class="vault-err">' + escapeHtml(message) + "</div>";
  }

  function showLoading(container) {
    container.innerHTML = '<div class="vault-loading">Loading episodes…</div>';
  }

  window.VaultEpisodes = {
    load: function () {
      var container = document.getElementById("vault-episodes");
      var token = getToken();
      if (token) setToken(token);
      if (!token) {
        showError(container, "Paste a Supabase access token above, then click Load episodes.");
        return;
      }
      showLoading(container);
      var podcast = document.getElementById("episodes-podcast")?.value || "";
      var apiBase = getApiBase();
      var url = apiBase + "/episodes?limit=100" + (podcast ? "&podcast=" + encodeURIComponent(podcast) : "");
      fetch(url, {
        method: "GET",
        headers: { Authorization: "Bearer " + token },
      })
        .then(function (r) {
          return r.json().then(function (j) {
            if (r.status === 401) {
              showError(container, "Invalid or expired token. Sign in again and paste a new token.");
            } else if (!r.ok) {
              showError(container, j.detail || r.status || "Request failed");
            } else {
              showEpisodes(container, j);
            }
          });
        })
        .catch(function (err) {
          showError(container, err.message || "Network error");
        });
    },
  };

  document.addEventListener("DOMContentLoaded", function () {
    var saved = sessionStorage.getItem(STORAGE_KEY);
    var el = document.getElementById("token");
    if (saved && el) el.value = saved;
  });
})();
