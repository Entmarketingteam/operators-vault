# Deploy Operators Vault on Vercel

The search UI is a static site in `web/` that calls the Railway API. To deploy on Vercel:

1. **Connect the repo**
   - Go to [vercel.com](https://vercel.com) and sign in.
   - Import this repository (GitHub/GitLab/Bitbucket).

2. **Set the root directory**
   - In the project: **Settings → General → Root Directory** set to `web`.
   - This makes Vercel serve `web/index.html`, `web/css/`, and `web/js/` as the site root.

3. **Deploy**
   - Leave **Build Command** and **Output Directory** empty (static site, no build).
   - Deploy. Your site will be at `https://<your-project>.vercel.app`.

4. **Optional: lock CORS to your domain**
   - On **Railway** (where the API runs), set env var:
     - `CORS_ORIGINS=https://<your-project>.vercel.app`
   - So only your Vercel origin can call the API (otherwise the API allows `*`).

**API:** The front end is configured to use `https://superb-smile-production.up.railway.app` for `/search`. To point at a different API, edit `window.VaultConfig.apiBase` in `web/index.html`.
