(function () {
  var STORAGE_KEY = "vault_token";
  function getToken() {
    return document.getElementById("token")?.value?.trim() || sessionStorage.getItem(STORAGE_KEY) || "";
  }
  function setToken(t) { sessionStorage.setItem(STORAGE_KEY, t); var e = document.getElementById("token"); if (e) e.value = t; }
  function escapeHtml(s) { if (!s) return ""; var d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function addMessage(container, role, text) {
    var div = document.createElement("div");
    div.className = role === "user" ? "vault-chat-user" : "vault-chat-bot";
    div.style.marginBottom = "1rem";
    div.style.padding = "0.75rem 1rem";
    div.style.borderRadius = "8px";
    div.style.background = role === "user" ? "var(--vault-bg-alt, #f5f5f5)" : "var(--vault-border, #eee)";
    var p = document.createElement("p");
    p.style.margin = "0";
    p.style.whiteSpace = "pre-wrap";
    p.textContent = text;
    div.appendChild(p);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
  }
  window.VaultAsk = {
    send: function () {
      var input = document.getElementById("vault-chat-input");
      var messages = document.getElementById("vault-chat-messages");
      var errEl = document.getElementById("vault-chat-error");
      var msg = (input && input.value || "").trim();
      if (!msg) return;
      var token = getToken();
      if (!token) { errEl.style.display = "block"; errEl.textContent = "Paste a Supabase access token in the header."; return; }
      setToken(token);
      errEl.style.display = "none";
      addMessage(messages, "user", msg);
      input.value = "";
      input.disabled = true;
      var apiBase = window.VaultConfig?.apiBase || "";
      fetch(apiBase + "/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify({ message: msg, context_limit: 10 }),
      })
        .then(function (r) { return r.json().then(function (j) {
          input.disabled = false;
          if (r.status === 401) { addMessage(messages, "bot", "Invalid or expired token. Paste a new token."); return; }
          if (!r.ok) { addMessage(messages, "bot", j.detail || "Request failed"); return; }
          addMessage(messages, "bot", (j.reply || "").trim() || "(No response.)");
        }); })
        .catch(function (err) { input.disabled = false; addMessage(messages, "bot", err.message || "Network error"); });
    },
  };
  document.addEventListener("DOMContentLoaded", function () {
    var s = sessionStorage.getItem(STORAGE_KEY), el = document.getElementById("token");
    if (s && el) el.value = s;
  });
})();
