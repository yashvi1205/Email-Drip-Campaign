# Email Campaign Tracker - Operational Runbooks

This guide provides step-by-step procedures for common operational issues.

---

## 🚨 Incident: Stuck Scraper Job
**Symptoms**: A job remains in `running` status for > 1 hour, and the dashboard shows no progress.

1.  **Verify Heartbeat**: Check `scraper_jobs` table for `last_heartbeat`. If it hasn't updated in 10 mins, the worker is likely dead.
2.  **Manual Cleanup**:
    *   Find the Job ID on the dashboard.
    *   Run the "Zombie Cleanup" by simply clicking "Start Scrape" (the system automatically cleans zombies on startup).
    *   Alternatively, run: `DELETE FROM scraper_jobs WHERE status = 'running' AND id = <job_id>;`
3.  **Check Logs**: Search `app.log` for the specific `job_id` to identify why it hung.

---

## 🔑 Incident: Expired LinkedIn Session
**Symptoms**: Scraper logs show "AUTHENTICATION REQUIRED" or "Redirected to login".

1.  **Immediate Fix**: 
    *   Disable Headless mode in `.env`: `HEADLESS=false`.
    *   Run the scraper locally: `python -m scraper.scrape_automation`.
    *   A browser window will open. **Manually log in** to LinkedIn.
    *   Solve any Captchas or 2FA challenges.
    *   Once the feed loads, close the browser.
2.  **Verify**: Re-enable `HEADLESS=true` and run a test job.

---

## 📉 Incident: Queue Backlog
**Symptoms**: New jobs are rejected with "Backlog too large".

1.  **Scale Workers**: Spin up more worker containers if resources allow.
2.  **Check for Fail-Loops**: Look for jobs that are `retrying` repeatedly. This usually indicates a profile block or a code bug.
3.  **Clear Queue (Nuclear Option)**:
    ```bash
    redis-cli flushall # Warning: This clears ALL redis data including rate limits
    ```

---

## 📁 Incident: Profile Corruption
**Symptoms**: Chrome fails to start with "User data directory in use" or "Profile error".

1.  **Release Lock**: If the Redis lock is stuck, run: `redis-cli del lock:profile:default_profile`.
2.  **Cleanup Files**:
    *   Navigate to the `data/browser_profiles` directory.
    *   Delete the `SingletonLock` file inside the profile folder.
3.  **Hard Reset**: If corruption persists, delete the entire profile folder and re-login (see Session Refresh flow above).

---

## 📈 Monitoring & Alerts
*   **Health Checks**: Monitor `http://backend:8001/api/health/readiness`.
*   **Worker Pulse**: Monitor `http://backend:8001/api/health/workers`.
*   **Queue Depth**: Monitor `http://backend:8001/api/health/queue`.

---

## 🛠️ Maintenance Flows
### 1. Database Migrations
Always backup your database before running migrations.
```bash
pg_dump email_campaign > backup_$(date +%F).sql
# Apply new script
psql email_campaign < Drip_Campaign_Database_Script.sql
```

### 2. Updating Browser
If the scraper fails with "Chrome version mismatch", update your Docker images:
```bash
docker-compose pull
docker-compose up -d --build worker
```
