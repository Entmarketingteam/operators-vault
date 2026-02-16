# Cron Runner – Operators Vault Sync

This folder is a **separate Railway service** that runs on a schedule and calls the main app’s `/trigger-sync` endpoint.

- **Schedule:** every 3 hours (`0 */3 * * *`), set in `railway.json`
- **Variable:** set `TRIGGER_URL` in Railway to your app URL, e.g.  
  `https://your-app.up.railway.app/trigger-sync`

Deploy via Railway → New → GitHub Repo → Root Directory: `cron-runner`.
