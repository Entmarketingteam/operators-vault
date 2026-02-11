/**
 * Operators Vault – search UI logic.
 * Uses Bearer token (from Supabase Auth or paste) for /search.
 */
(function () {
  const STORAGE_KEY = 'vault_token';

  function getToken() {
    if (window.VaultAuth && typeof window.VaultAuth.getToken === 'function') {
      var t = window.VaultAuth.getToken();
      if (t) return t;
    }
    return document.getElementById('token')?.value?.trim() || sessionStorage.getItem(STORAGE_KEY) || '';
  }

  function setToken(token) {
    sessionStorage.setItem(STORAGE_KEY, token);
    const el = document.getElementById('token');
    if (el) el.value = token;
  }

  function getApiBase() {
    return window.VaultConfig?.apiBase || '';
  }

  function buildSearchParams(formData) {
    const params = new URLSearchParams();
    if (formData.get('q')) params.set('q', formData.get('q'));
    if (formData.get('podcast')) params.set('podcast', formData.get('podcast'));
    if (formData.get('category')) params.set('category', formData.get('category'));
    if (formData.get('type_')) params.set('type_', formData.get('type_'));
    params.set('limit', formData.get('limit') || '20');
    return params;
  }

  function formatDuration(sec) {
    if (sec == null) return '';
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
  }

  function escapeHtml(s) {
    if (!s) return '';
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function renderSnippet(html) {
    if (!html) return '';
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || html;
  }

  function buildYouTubeUrl(videoId, startSec) {
    if (!videoId) return '#';
    let url = 'https://www.youtube.com/watch?v=' + videoId;
    if (startSec != null) url += '&t=' + Math.round(startSec);
    return url;
  }

  /** Strip redundant "Operators Titans" / "Operator Titans" prefix when podcast is titans. */
  function titleForDisplay(rawTitle, podcast) {
    if (!rawTitle || (podcast || '').toLowerCase() !== 'titans') return rawTitle;
    var t = rawTitle.replace(/^\s*Operators?\s+Titans\s*[-:\s]*/i, '').trim();
    return t || rawTitle;
  }

  function renderHit(h) {
    const isMoment = h.type === 'moment';
    const rawTitle = isMoment
      ? (h.speaker_label || 'Segment')
      : (h.title || h.headline_title || '(no title)');
    const title = isMoment ? rawTitle : titleForDisplay(rawTitle, h.podcast);
    const snippet = isMoment
      ? (h.headline || h.text || '')
      : (h.headline_description || h.description || '');
    const podcastLabel = (h.podcast || '').replace(/_/g, ' ');
    const category = h.category || '';
    const startSec = h.start_time_sec;
    const watchUrl = buildYouTubeUrl(h.video_id, startSec);
    const watchLabel = startSec != null ? 'Watch @ ' + formatDuration(startSec) : 'Watch';

    const pillClass = isMoment ? 'vault-pill vault-pill-moment' : 'vault-pill';
    const pillText = isMoment ? 'Moment' : (category || 'Insight');

    return (
      '<div class="vault-card">' +
      '<div class="vault-card-header">' +
      '<h3 class="vault-card-title">' + escapeHtml(title) + '</h3>' +
      '<span class="' + pillClass + '">' + escapeHtml(pillText) + '</span>' +
      '</div>' +
      '<p class="vault-card-meta">' +
      escapeHtml(podcastLabel) +
      (category && !isMoment ? ' · ' + escapeHtml(category) : '') +
      ' · <a href="' + escapeHtml(watchUrl) + '" target="_blank" rel="noopener">' + escapeHtml(watchLabel) + '</a>' +
      '</p>' +
      (snippet ? '<p class="vault-card-snippet">' + renderSnippet(snippet).substring(0, 400) + (snippet.length > 400 ? '…' : '') + '</p>' : '') +
      '<a href="' + escapeHtml(watchUrl) + '" target="_blank" rel="noopener" class="vault-watch-btn">▶ ' + watchLabel + '</a>' +
      '</div>'
    );
  }

  function showResult(outEl, data) {
    const total = data.total || 0;
    const hits = data.hits || [];
    let html = '<div class="vault-results-header"><span class="vault-results-count"><strong>' + total + '</strong> result' + (total === 1 ? '' : 's') + '</span></div>';
    if (hits.length) {
      html += '<div class="vault-results-list">';
      hits.forEach(function (h) {
        html += renderHit(h);
      });
      html += '</div>';
    } else {
      html += '<p class="vault-empty">No results. Try a different query or filters.</p>';
    }
    outEl.innerHTML = html;
  }

  function showError(outEl, message) {
    outEl.innerHTML = '<div class="vault-err">' + escapeHtml(message) + '</div>';
  }

  function showLoading(outEl) {
    outEl.innerHTML = '<div class="vault-loading">Searching…</div>';
  }

  window.VaultSearch = function () {
    const form = document.getElementById('vault-search-form');
    const out = document.getElementById('vault-results');
    if (!form || !out) return;

    const token = getToken();
    if (token) setToken(token);
    if (!token) {
      showError(out, 'Sign in above (Google or magic link) or paste a Supabase access token to search.');
      return;
    }

    showLoading(out);
    const formData = new FormData(form);
    const params = buildSearchParams(formData);
    const apiBase = getApiBase();
    const url = apiBase + '/search?' + params.toString();

    fetch(url, {
      method: 'GET',
      headers: { 'Authorization': 'Bearer ' + token },
    })
      .then(function (r) {
        return r.json().then(function (j) {
          if (r.status === 401) {
            showError(out, 'Invalid or expired token. Sign in again and paste a new token.');
          } else if (!r.ok) {
            showError(out, j.detail || r.status || 'Request failed');
          } else {
            showResult(out, j);
          }
        });
      })
      .catch(function (err) {
        showError(out, err.message || 'Network error');
      });
  };

  window.VaultSetToken = setToken;
  window.VaultGetToken = getToken;

  // Restore token from session on load
  document.addEventListener('DOMContentLoaded', function () {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    const el = document.getElementById('token');
    if (saved && el) el.value = saved;
  });
})();
