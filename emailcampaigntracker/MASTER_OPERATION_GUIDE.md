# 🚀 Master Operation Guide: Email Drip Campaign

This guide explains how to run, maintain, and troubleshoot the system on any computer (Windows, Mac, or Linux).

---

## 🔑 LinkedIn Authentication (The JSON Bridge)

If you are running on Windows but using Docker (Linux), you must bridge the encryption gap to stay logged in.

### 1. Initial Login (On Windows)
Run the following command on your host machine:
```bash
python export_cookies.py
```
*   A browser will open.
*   Log in to LinkedIn manually.
*   Once you see your feed, go back to the terminal and press **Enter**.
*   This creates `cookies.json` in your project root.

### 2. Launching the System
```bash
docker compose up --build
```
The scraper will automatically detect `cookies.json`, inject your session, and start working. You won't need to do this again unless your session expires.

---

## 📦 1. Daily Startup (Local Development)
To start the entire system, open your terminal in the project folder and run:

```bash
docker compose up --build
```

**What this starts:**
*   **API (Port 8000)**: The brain of the system.
*   **Frontend (Port 5173)**: Your dashboard.
*   **Worker**: The background scraper.
*   **Database & Redis**: The storage and messenger.

---

## 🔗 2. The Tunnel (Public Access)
If you need **n8n** or **External Tracking** to work with your local computer, you must start a tunnel.

1.  Open a **new terminal**.
2.  Run:
    ```bash
    npx untun@latest tunnel http://localhost:8000
    ```
3.  **IMPORTANT**: This will give you a new link every day (e.g., `https://random-word.untun.io`).
4.  **Daily Actions**: Because the link changes daily, you MUST:
    *   **Update n8n**: Update any n8n HTTP nodes to point to the new link.
    *   **Update .env**: If running the scraper locally, update `BACKEND_INTERNAL_URL` in your `.env` to the new tunnel link or `http://localhost:8000`.

---

## 🔑 3. Fixing "Authentication Required" (LinkedIn Login)
If the Docker logs show a session error, follow these steps to refresh your login:

1.  Stop Docker (`Ctrl + C`).
2.  Run the scraper locally in "Manual Mode":
    ```bash
    # Windows
    .venv\Scripts\activate
    python -m scraper.scrape_automation

    # Mac/Linux
    source .venv/bin/activate
    python3 -m scraper.scrape_automation
    ```
3.  A browser will open. **Log in to LinkedIn manually.**
4.  Once your feed loads, you can close the browser and restart Docker. The session is now saved in `C:\selenium-profile` (or your mapped folder) and shared with Docker.

---

## 🌍 4. Deploying to Production (Render)
When you are ready to push changes to the live site:

1.  **Git Push**:
    ```bash
    git add .
    git commit -m "Update features"
    git push origin main
    ```
2.  **Redis**: Ensure your `REDIS_URL` in Render matches your **Upstash** or **Render Redis** link.
3.  **Start Command**: Ensure Render is using the "Combined" command:
    `sh -c "python -m app.workers.scraper_worker & uvicorn app.main:app --host 0.0.0.0 --port 8000"`

---

## 🛠️ 5. Troubleshooting
*   **Database Mismatch**: If you clear your database, run:
    `docker exec -it emailcampaign_api python -m alembic upgrade head`
*   **Docker Conflicts**: If you get a "Container name in use" error, run:
    `docker rm -f emailcampaign_api emailcampaign_worker emailcampaign_redis emailcampaign_db emailcampaign_frontend`
*   **Vite Not Found**: If the frontend crashes, ensure your `docker-compose.yml` includes the `npm install` command.

---

**This system is now 100% containerized and ready for any environment!**
