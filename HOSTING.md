# Hosting Operators Vault (like mfmvault.com)

Get the app live at a custom domain so people can use the search UI and n8n can keep syncing.

---

## Current state

- **Railway app:** https://superb-smile-production.up.railway.app  
  - `/health` ok, `POST /sync` works, n8n **Operators Vault – Sync New Episodes** is Active (every 6h).
- **Missing for “like mfmvault.com”:**
  1. **Custom domain** (e.g. `operatorsvault.com` or `vault.yourdomain.com`) so the app has a stable, branded URL.
  2. **Search working** so `GET /search` and **`/search-ui`** work (fix `MEILISEARCH_API_KEY` on Railway if you still see `invalid_api_key`).

---

## 1. Add a custom domain on Railway

1. Open [Railway](https://railway.app) → your project → the **Operators Vault** service.
2. Go to **Settings** → **Public Networking** → **Custom Domain** → **+ Add custom domain**.
3. Enter your domain, e.g.:
   - `operatorsvault.com` (root), or  
   - `vault.yourdomain.com` (subdomain), or  
   - `www.operatorsvault.com`.
4. Railway will show a **CNAME target** (e.g. `xxxx.up.railway.app`). Leave this tab open.

---

## 2. Point DNS at Railway

At your DNS provider (Cloudflare, Namecheap, Vercel DNS, etc.):

- **Subdomain** (e.g. `vault.yourdomain.com`):  
  Add a **CNAME** record:  
  - Name: `vault` (or the subdomain you chose)  
  - Target: the Railway CNAME value (e.g. `xxxx.up.railway.app`).

- **Root domain** (e.g. `operatorsvault.com`):  
  Standard DNS does not allow CNAME at the root. Use one of:
  - **CNAME flattening** (Cloudflare, etc.): add a CNAME for `@` pointing to Railway’s target, or  
  - **ALIAS / ANAME** record pointing to Railway’s target if your provider supports it.

Save the DNS record. Propagation can take from a few minutes up to 24–48 hours.

---

## 3. Verify on Railway

Back in Railway → **Custom Domain**:

- Wait until the domain shows as **Verified** (green check).
- Railway will issue an SSL certificate automatically (Let’s Encrypt).

Your app will then be available at:

- `https://your-domain.com/` (API root)
- `https://your-domain.com/search-ui` (search UI – main public page)
- `https://your-domain.com/health`
- `https://your-domain.com/search?q=...`

---

## 4. Fix search (if needed)

If `GET /search` or `/search-ui` returns `invalid_api_key`:

1. In **Meilisearch** (Cloud or self‑hosted), create or choose an API key that has **search** (and index) on the `operators_insights` index.
2. In **Railway** → your service → **Variables**, set:
   - `MEILISEARCH_HOST` = your Meilisearch URL (e.g. `https://ms-xxxx.meilisearch.io`)
   - `MEILISEARCH_API_KEY` = the key from step 1.
3. Or from the repo (with `RAILWAY_API_TOKEN`, `MEILISEARCH_HOST`, `MEILISEARCH_API_KEY` in `.env`):  
   `python scripts/set_railway_meilisearch.py`
4. Redeploy or wait for Railway to pick up the new variables, then try `https://your-domain.com/search?q=test` and `https://your-domain.com/search-ui`.

Details: `meilisearch-setup.md` → “Fix `/search` on Railway”.

---

## 5. Point n8n at the custom domain (optional)

n8n can keep using the Railway default URL (`https://superb-smile-production.up.railway.app`) if you prefer. To use the custom domain instead:

1. In n8n, open the **Operators Vault – Sync New Episodes** workflow.
2. In the HTTP Request node that calls the API, change the URL from  
   `https://superb-smile-production.up.railway.app/sync`  
   to  
   `https://your-domain.com/sync`.
3. Save and ensure the workflow is still **Active**.

You can also re-run `python scripts/setup_n8n_workflows.py` after setting `RAILWAY_APP_URL=https://your-domain.com` in `.env`, so future imports/updates use the custom domain.

---

## Checklist (like mfmvault.com)

- [ ] Custom domain added in Railway and DNS pointing to Railway.
- [ ] Domain verified and SSL active on Railway.
- [ ] `MEILISEARCH_API_KEY` (and `MEILISEARCH_HOST`) set on Railway so `/search` and `/search-ui` work.
- [ ] `https://your-domain.com/search-ui` loads and search works.
- [ ] (Optional) n8n sync URL updated to `https://your-domain.com/sync` or `RAILWAY_APP_URL` set and `setup_n8n_workflows.py` re-run.

After this, the app is hosted and usable at your domain in the same way as mfmvault.com (custom URL + working search UI + n8n sync).
