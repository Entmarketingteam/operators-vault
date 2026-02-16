# Where is the cron job on Railway?

The **cron is a separate service**, not inside superb-smile.

- **Project:** operators-vault  
- **Services in the project:**
  1. **superb-smile** – your main API (sync, process, health).
  2. **vault-sync-cron** – the cron job that calls `POST /sync/async` every 3 hours.

In the Railway dashboard:

1. Open the **operators-vault** project.
2. You should see **two service cards**: **superb-smile** and **vault-sync-cron**.
3. Click **vault-sync-cron** to see its deployments, variables, and **Cron Runs** (schedule and run history).

If you only see superb-smile, use **+ New** in the project to add a service, or run:

```bash
python scripts/create_railway_cron_service.py
```

(If it says "already exists", the service is there; scroll or look for a second card. To just fix its URL/schedule: `python scripts/find_and_fix_cron.py`.)
