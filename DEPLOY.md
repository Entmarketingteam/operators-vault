# Deploy Operators Vault on Vercel

The search UI is a static site in `web/` that calls the Railway API.

---

## One-time setup (Vercel)

1. **Connect the repo** at [vercel.com](https://vercel.com) → Import this repository.
2. **Root directory:** **Settings → General → Root Directory** → set to `web` → Save.
3. Deploy (no build command or output dir needed). Your site: `https://<your-project>.vercel.app`.

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

**API URL:** The front end uses `https://superb-smile-production.up.railway.app`. To change it, edit `window.VaultConfig.apiBase` in `web/index.html`.
