# Deploy Operators Vault on Vercel

The static front end in `web/` calls the Railway API. Nav links (Discover, Listen, Catalog, People, Ask, API) point to Railway-hosted pages (`/search-ui`, `/episodes-ui`, `/insights-ui`, `/people-ui`, `/ask-ui`, `/docs`). Pushing to GitHub updates both Railway (API + all UIs) and Vercel (this `web/` site) when the repo is connected to both.

---

## One-time setup (Vercel)

1. **Connect the repo** at [vercel.com](https://vercel.com) → Import this repository.
2. **Root directory:** **Settings → General → Root Directory** → set to `web` → Save.
3. **Supabase sign-in (no more pasting tokens):**
   - In Vercel: **Settings → Environment Variables** add:
     - **Name:** `SUPABASE_ANON_KEY`  
     - **Value:** your Supabase **anon public** key (Supabase → Project → **Settings → API** → Project API keys → **anon public**).
   - **Settings → Build and Deployment → Build Command** set to: `node inject-env.js`  
   - Redeploy. Users can then **Sign in with Google** or **Send magic link** on the site; no token paste needed.
4. Your site is at `https://<your-project>.vercel.app`.

---

## Post-deploy: Railway + Vercel (do these once)

### 1. Railway – restrict API to your front end (CORS)

1. Open [Railway](https://railway.app) → your **operators-vault** project → **Variables**.
2. Add a variable:
   - **Name:** `CORS_ORIGINS`
   - **Value (copy exactly):**  
     `https://operators-vault-2wjca77d9-ethan-atchleys-projects.vercel.app,https://operators-vault.vercel.app`
3. Save. Railway will redeploy the API; after that only these origins can call `/search`.

*(If you use a custom domain on Vercel later, add it to the same value, comma-separated.)*

### 2. Vercel – optional custom domain

1. In Vercel: **operators-vault** → **Settings → Domains**.
2. Add your domain (e.g. `vault.yourcompany.com`).
3. Follow the DNS instructions Vercel shows (add the CNAME or A record they give you).
4. After DNS propagates, add that domain to Railway `CORS_ORIGINS` as well (comma-separated).

---

**Supabase redirect:** In Supabase → **Authentication → URL Configuration**, set **Site URL** to your Vercel URL (e.g. `https://operators-vault.vercel.app`) and add the same URL under **Redirect URLs** so Google and magic-link sign-in work.

**API URL:** The front end uses `window.VaultConfig.apiBase` in `web/index.html` (default `https://superb-smile-production.up.railway.app`). Nav links are built from this base so Listen, Catalog, People, and Ask open the Railway-hosted UIs. To use a different API URL, set it in `web/index.html` or inject via build (e.g. `inject-env.js` with `NEXT_PUBLIC_VAULT_API_BASE` or similar).
