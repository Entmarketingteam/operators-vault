/**
 * Operators Vault – Supabase Auth in the browser.
 * Set window.VaultConfig.supabaseUrl and supabaseAnonKey in index.html.
 * Provides VaultAuth.getToken(), signInWithGoogle(), signInWithMagicLink(), signOut(), and UI updates.
 */
(function () {
  var currentToken = '';
  var supabase = null;

  function getConfig() {
    var c = window.VaultConfig || {};
    return { url: c.supabaseUrl || '', anonKey: c.supabaseAnonKey || '' };
  }

  function updateUI() {
    var authEl = document.getElementById('vault-auth-state');
    var tokenWrap = document.getElementById('vault-token-wrap');
    var signedInEl = document.getElementById('vault-signed-in');
    var signInEl = document.getElementById('vault-sign-in');
    if (!authEl) return;

    if (currentToken && supabase) {
      supabase.auth.getUser().then(function (r) {
        var user = r.data?.user;
        var email = user?.email || 'Signed in';
        var emailEl = document.getElementById('vault-signed-in-email');
        if (emailEl) emailEl.textContent = email;
        if (signedInEl) signedInEl.style.display = '';
        if (signInEl) signInEl.style.display = 'none';
        if (tokenWrap) tokenWrap.style.display = 'none';
      }).catch(function () {
        currentToken = '';
        if (signedInEl) signedInEl.style.display = 'none';
        if (signInEl) signInEl.style.display = '';
        if (tokenWrap) tokenWrap.style.display = '';
      });
    } else {
      if (signedInEl) signedInEl.style.display = 'none';
      if (signInEl) signInEl.style.display = '';
      if (tokenWrap) tokenWrap.style.display = (getConfig().url && getConfig().anonKey) ? 'none' : '';
    }
  }

  function setTokenFromSession(session) {
    currentToken = session?.access_token || '';
    var el = document.getElementById('token');
    if (el) el.value = currentToken;
    if (currentToken) {
      try { sessionStorage.setItem('vault_token', currentToken); } catch (e) {}
    }
    updateUI();
  }

  function init() {
    var config = getConfig();
    if (!config.url || !config.anonKey) {
      window.VaultAuth = {
        getToken: function () { return document.getElementById('token')?.value?.trim() || sessionStorage.getItem('vault_token') || ''; },
        signInWithGoogle: function () {},
        signOut: function () {},
        isConfigured: function () { return false; }
      };
      updateUI();
      return;
    }

    function doInit() {
      if (typeof window.createSupabaseClient !== 'function') {
        setTimeout(doInit, 30);
        return;
      }
      window.createSupabaseClient(config.url, config.anonKey).then(function (client) {
      supabase = client;
      supabase.auth.getSession().then(function (_ref) {
        var session = _ref.data.session;
        setTokenFromSession(session);
      });
      supabase.auth.onAuthStateChange(function (event, session) {
        setTokenFromSession(session);
      });

      window.VaultAuth = {
        getToken: function () { return currentToken || document.getElementById('token')?.value?.trim() || sessionStorage.getItem('vault_token') || ''; },
        signInWithGoogle: function () {
          supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin + window.location.pathname } });
        },
        signInWithMagicLink: function (email) {
          if (!email || !email.trim()) return Promise.reject(new Error('Enter your email'));
          return supabase.auth.signInWithOtp({ email: email.trim(), options: { emailRedirectTo: window.location.origin + window.location.pathname } });
        },
        signOut: function () {
          currentToken = '';
          if (supabase) supabase.auth.signOut();
          try { sessionStorage.removeItem('vault_token'); } catch (e) {}
          var el = document.getElementById('token');
          if (el) el.value = '';
          updateUI();
        },
        isConfigured: function () { return true; }
      };
      updateUI();
      }).catch(function (err) {
      console.error('Supabase init error', err);
      window.VaultAuth = {
        getToken: function () { return document.getElementById('token')?.value?.trim() || sessionStorage.getItem('vault_token') || ''; },
        signInWithGoogle: function () {},
        signOut: function () {},
        isConfigured: function () { return false; }
      };
      updateUI();
      });
    }
    doInit();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
