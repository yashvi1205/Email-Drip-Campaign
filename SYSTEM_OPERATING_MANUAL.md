# 📘 LinkedIn Scraper & Email Tracking: Operating Manual

This document provides the necessary guidelines and technical instructions for operating and testing the Email Drip Campaign system.

---

## 🛡️ 1. Safety & Account Protection (Anti-Block Rules)
LinkedIn uses advanced bot detection. To ensure the safety of the LinkedIn account, follow these strictly:

*   **Daily Quota:** Do not exceed **70 profile scrapes per 24 hours**.
*   **Human Delays:** The system uses randomized delays (10-25 seconds) between profile visits. Do not reduce these.
*   **Browser Usage:** Avoid manually clicking or searching on LinkedIn while the scraper is active in the background.
*   **Account Warming:** If using a new account, start with 10-15 profiles per day and gradually increase over 2 weeks.

---

## ⚙️ 2. Technical Setup & Execution
The system requires five components running simultaneously.

### 🖥️ Terminals Required:

1.  **Backend API (Port 8001):**
    ```bash
    uvicorn api.main:app --reload --port 8001
    ```
2.  **Background Worker (The Scraper):**
    ```bash
    python -m app.workers.scraper_worker
    ```
3.  **Frontend Dashboard:**
    ```bash
    cd frontend
    npm run dev
    ```
4.  **Public Tunnel (For n8n Webhooks):**
    ```bash
    npx untun@latest tunnel http://localhost:8001
    ```
5.  **Services:**
    *   **Redis:** Ensure the Redis service is running (`redis-server`).
    *   **Database:** Ensure PostgreSQL is running.

---

## 🏗️ 3. Core Technology Stack (Architecture)
To build a professional, non-blocking system, we use the following key libraries:

### **1. Redis (The Message Broker)**
*   **Why?** Scraping takes time (1-2 minutes). We cannot make the user wait for the API to finish. 
*   **Role:** Redis acts as a "Waiting Room." The API puts a job in Redis, and the Background Worker picks it up when it's ready.

### **2. Alembic (Database Migrations)**
*   **Why?** When we change the database structure (e.g., adding a "Clicked" status), we need a safe way to update the database without losing data.
*   **Role:** Alembic tracks every change to your tables via `alembic upgrade head`.

### **3. untun & Render (The "Hybrid" Connection)**
*   **The Problem:** Your local computer (localhost) is invisible to the internet. 
*   **The Solution:** 
    *   **Render:** Hosts the public tracking links so recipients can reach them from anywhere.
    *   **untun:** Creates a secure "Bridge" from Render back to your local computer. When someone clicks a link on Render, **untun** carries that data back to your local database instantly.

---

## 🔄 3. n8n Workflow Integration
The automation flows as follows:

1.  **Discovery:** n8n identifies a profile URL to be scraped.
2.  **Trigger:** n8n calls the Backend API: `POST /api/scrape?webhook_url=...`
3.  **Execution:** The API queues a job in Redis. The **Worker** executes the scrape using an automated browser.
4.  **Data Persistence:** The Worker saves lead info (Role, Company, Headline, Activity) into the PostgreSQL database.
5.  **Callback:** The Worker sends a JSON payload of the results back to n8n's webhook.
6.  **Delivery:** n8n processes the data and sends the personalized drip email.

---

## ⚠️ 4. Critical Daily Maintenance (Tunnel Setup)
Because the **Public Tunnel (untun)** provides a new URL every time it is started, you must perform this step **every morning** to keep the tracking system active:

1.  **Start the Tunnel:** Run `npx untun@latest tunnel http://localhost:8001` in Terminal 4.
2.  **Copy the New URL:** Look for the link ending in `.untun.com`.
3.  **Update Render:** 
    *   Go to your **Render Dashboard**.
    *   Go to **Environment Variables**.
    *   Update `LOCAL_BACKEND_URL` with your new Tunnel URL.
    *   Save and wait for Render to redeploy.

> [!CAUTION]
> If you skip this step, clicks and opens will **not** be recorded in your local database.

---

## 🏗️ Phase 1: Production Hardening (Docker & Profiles)
The system is now fully containerized and cross-platform. 

### 🐋 1. Docker Setup (Production)
To run the scraper in a production-ready Linux environment:
1.  **Build the Image:** `docker build -t scraper-worker -f Dockerfile.worker .`
2.  **Run with Persistence:**
    ```bash
    docker run -v scraper_profiles:/app/data/browser --env-file .env scraper-worker
    ```
    *Note: The volume `scraper_profiles` ensures your LinkedIn session stays alive even if the container is deleted.*

### 📂 2. Profile Management
Instead of using your personal browser, the system now uses dedicated "Browser Profiles":
*   **Windows Default:** `C:\selenium-profile\Default`
*   **Linux/Docker Default:** `/app/data/browser/Default`
*   **Configuring Multiple Accounts:** Use the `LINKEDIN_PROFILE_NAME` env var to switch between accounts (e.g., `LINKEDIN_PROFILE_NAME=Account_A`).

### 🔑 3. Session Refresh Process
If the scraper logs an **"AUTHENTICATION REQUIRED"** error:
1.  **Local (Windows/Mac):** Run the scraper in "Headful" mode (`HEADLESS=false`), log in manually to LinkedIn when the browser opens, and then close it. The session is now saved.
2.  **Remote (Server):** 
    *   **Option A:** Use a browser extension (like *EditThisCookie*) to export cookies from your laptop and paste them into the `cookies.pkl` backup on the server.
    *   **Option B:** Temporarily run the container with a VNC/Desktop interface to log in manually.

### 🩺 4. Scraper Diagnostics
Every time the scraper starts, it prints a **Diagnostic Block**:
*   **OS Type:** Confirms if it's running on Windows or Linux.
*   **Binary Path:** Shows which Chrome/Chromium version is being used.
*   **Session State:** Confirms if the LinkedIn login is still valid before starting.

---

## 🧪 5. Testing & Verification Guide
To verify the system is working correctly for seniors:

### A. Scraper Verification
*   **Logs:** Check the Worker terminal. You should see real-time extraction logs including company name and profile headline.
*   **Status File:** Check `scraper_status.json` in the root folder to see the most recent job result.

### B. Dashboard Verification
*   Visit `http://localhost:5173/dashboard`.
*   Verify that leads appear in the list with the correct **Status** (Sent/Opened/Clicked).

### C. Tracking Verification
*   **Open Tracking:** Send a test email. When the recipient opens the email, the dashboard status should update to **OPENED**.
*   **Click Tracking:** Click any link in the test email. The terminal should print `[DEBUG] CLICK DETECTED!` and the dashboard should update to **CLICKED**.

---

## 🛠️ 5. Troubleshooting
*   **"Internal Server Error" on Clicks:** Ensure the `LOCAL_BACKEND_URL` in the Render environment is set to the current Tunnel URL.
*   **Scraper Hangs:** Use the `python reset_scraper.py` utility to clear stuck jobs and Redis locks.
