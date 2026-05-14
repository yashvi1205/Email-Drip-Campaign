# 🚀 Email Drip Campaign: Master Operation Guide

This guide contains everything you need to run, maintain, and troubleshoot the system daily.

---

## 🗓️ 1. Daily Startup Routine (The "Morning Check")

Follow these steps every morning to ensure the system is healthy:

### **A. Refresh your LinkedIn Session**
LinkedIn sessions can expire. To ensure the scraper has access:
1. Open your terminal on your Windows machine.
2. Go to the project folder: `cd emailcampaigntracker`
3. Run the cookie exporter:
   ```bash
   python export_cookies.py
   ```
   *Note: If a Chrome window opens, log in manually if needed, then close it. The script will save `cookies.json` automatically.*

### **B. Start the System**
Launch the Docker stack:
```bash
docker compose up --build
```

### **C. Access the Dashboard**
Open your browser to: **[http://127.0.0.1:5173](http://127.0.0.1:5173)**

---

## 🔐 2. Authentication Management (If Session Expires)

If you see **"AUTHENTICATION REQUIRED"** or **"Login Challenged"** in the logs:

1. **Stop Docker**: Press `Ctrl + C` in the terminal.
2. **Run Exporter**: Run `python export_cookies.py`.
3. **Manual Login**: When the browser opens, log in to LinkedIn manually and solve any CAPTCHAs.
4. **Restart**: Run `docker compose up --build` again. The new `cookies.json` will be injected into the container automatically.

---

## 📺 3. Monitoring & Logs

How to see what the system is doing:

| Action | Command |
| :--- | :--- |
| **Watch the Scraper** | `docker logs -f emailcampaign_worker` |
| **Watch the API** | `docker logs -f emailcampaign_api` |
| **Watch the Frontend** | `docker logs -f emailcampaign_frontend` |
| **Check Database** | Use the Dashboard "Leads" tab. |

---

## ☁️ 4. Deployment & Updates (Render/GitHub)

### **A. Pushing Code Updates**
When you change the code and want it on Render:
1. Go to the root `C:\git`.
2. Run:
   ```bash
   git add .
   git commit -m "Your update message"
   git push origin main --force
   ```

### **B. Update n8n Webhook (Untun/Tunnel)**
If your local n8n URL changes (e.g., you restarted your tunnel):
1. Open `.env` in the project root.
2. Update `N8N_WEBHOOK_URL` with the new link.
3. Restart Docker: `docker compose up --build`.

---

## 🛠️ 5. Troubleshooting Common Issues

| Issue | Solution |
| :--- | :--- |
| **"Connection Refused" (n8n)** | Ensure n8n is running on your Windows host and `.env` uses `host.docker.internal`. |
| **"Empty Response" (Frontend)** | Use `http://127.0.0.1:5173` instead of `localhost`. |
| **Duplicate Profiles** | The system now auto-deduplicates based on the LinkedIn URL. |
| **Scraper Stuck** | Restart the worker: `docker restart emailcampaign_worker`. |

---

## 📁 6. Important Files

- `cookies.json`: Your encrypted session "bridge" (DO NOT SHARE).
- `docker-compose.yml`: Controls all services (API, Worker, DB, Redis).
- `scraper/scrape_automation.py`: The "Brain" of the scraper.
- `.env`: Contains all your secret keys and URLs.

---
*Last Updated: 2026-05-14*
