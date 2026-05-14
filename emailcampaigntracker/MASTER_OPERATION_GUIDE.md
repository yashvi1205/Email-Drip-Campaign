# 🚀 Email Drip Campaign: Master Operation Guide

This guide contains everything you need to run, maintain, and troubleshoot the system daily.

---

## ⚠️ Safety & Limits (VERY IMPORTANT)

LinkedIn has strict automation detection. To keep your account safe, follow these rules:

- **The Rule of 50**: Never scrape more than **50 profiles per day**.
- **The "Human" Look**: Do not run the scraper multiple times in a row without a break.
- **Risk of Ban**: If you exceed 50+ profiles daily, LinkedIn may permanently **BAN** your account. The scraper has built-in delays, but the total volume is what LinkedIn monitors.
- **Warm-up**: If your account is new to scraping, start with only **10-15 profiles per day** and slowly increase.

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

## 🌍 4. Public Access & Tracking (Untun + Render)

For email tracking to work while you are developing locally, Render needs to "Talk" to your local machine.

### **Step A: Start the Tunnel**
1. Open a **new** terminal (keep Docker running in the other one).
2. Run the tunnel command:
   ```bash
   untun 8000
   ```
3. Copy the **Public URL** it gives you (e.g., `https://random-words.untun.com`).

### **Step B: Update Render**
1. Log in to your **Render Dashboard**.
2. Go to your **API Service** -> **Environment**.
3. Update the `LOCAL_BACKEND_URL` variable with your new Untun link.
4. **Save Changes**. Render will redeploy and now "knows" how to find your local machine!

### **Step C: Update n8n (Optional)**
If you are using n8n for email preparation, make sure the n8n webhook URL in your `.env` is also updated if the tunnel for n8n changed.

---

## 🧹 5. Preventing Duplicates (n8n vs Backend)

If you see the same person twice on your dashboard, it's usually because n8n is talking directly to the database and bypassing the "Smart Cleaner."

### **The Rule**
- **ALWAYS** use the Backend API to save leads.
- In n8n, use an **HTTP Request** node to call `POST http://localhost:8000/api/leads`.
- **NEVER** use the Postgres node to `INSERT` leads directly. The Backend API has the "Cleaner" logic that prevents duplicates; the database does not.

### **How to Fix Existing Duplicates**
If you already have duplicates, run the cleanup script:
```bash
python scratch/db_cleanup.py
```
This will merge your leads and keep your dashboard clean.

---

## 🛠️ 6. Troubleshooting Common Issues

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
