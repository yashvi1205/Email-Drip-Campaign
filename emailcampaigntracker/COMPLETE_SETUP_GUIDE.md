# 🚀 Email Drip Campaign: Complete Setup & Operational Guide

This document is a comprehensive, end-to-end guide to set up, run, and maintain the LinkedIn Scraper & AI Email Drip Campaign system on a new machine from scratch.

---

## 🏗️ 1. Architecture Overview

The system consists of the following components:
- **FastAPI Backend (port `8000`)**: Exposes API endpoints, handles webhooks, runs daily follow-ups (Workflow 3), and Gmail reply polling (Workflow 4).
- **React/Vite Frontend (port `5173`)**: Dashboard to monitor scraping activity, review leads, and trigger campaigns.
- **Redis Cache (port `6379`)**: Manages the scraping queue and coordinates background jobs.
- **PostgreSQL Database (port `5432`)**: Stores lead data, sent email sequences, events, and jobs.
- **Scraper Worker (runs on Host machine)**: Controls Google Chrome via Selenium to scrape LinkedIn profiles. Runs on the Windows host (not in Docker) to utilize local session cookies and browser profiles.

```mermaid
graph TD
    Dashboard[React Frontend: port 5173] -->|API Request| API[FastAPI Backend: port 8000]
    API -->|Enqueue Job| Redis[Redis: port 6379]
    Worker[Scraper Worker: Windows Host] -->|Listen to Queue| Redis
    Worker -->|Selenium/Chrome| LinkedIn[LinkedIn Profiles]
    Worker -->|Post Scraped Data| APIWeb[API Webhook /webhook/scraper-callback]
    APIWeb -->|Workflow 1: Dedup & Process| DB[(Postgres Database)]
    APIWeb -->|Workflow 2: AI Generate & Send| Gemini[Gemini API]
    APIWeb -->|Workflow 2: Send| Gmail[Gmail API]
```

---

## 🛠️ 2. Prerequisites

Ensure you have the following installed on the host machine:
1. **Docker Desktop** (with WSL2 backend enabled)
2. **Python 3.10+** (with `pip`)
3. **Node.js 18+** (with `npm`)
4. **Google Chrome** (latest version)
5. **Untun** (`npm install -g untun` or run via `npx untun`)

---

## ⚙️ 3. First-Time Setup & Configuration

### Step A: Clone & Set Up Local Environment
1. Open PowerShell or Terminal and go to the project root:
   ```bash
   cd emailcampaigntracker
   ```
2. Create and activate a Python virtual environment:
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

### Step B: Configure Google Cloud Console APIs
You need to set up Google APIs for Google Sheets (Service Account) and Gmail (OAuth2 client).

#### 📊 Part 1: Google Sheets (Service Account)
1. Go to the [Google Cloud Console](https://console.cloud.google.com).
2. Create a new project (e.g., `email-drip-campaign`).
3. Enable the **Google Sheets API** and **Google Drive API** from the API Library.
4. Go to **Credentials → Create Credentials → Service Account**.
   - Assign the **Editor** role to the service account.
5. In the Service Account settings, go to the **Keys** tab → **Add Key → Create New Key** → Select **JSON**. Save the downloaded JSON file.
6. Open your target Google Sheet. Click **Share** (top-right) and share it with the service account's email address (e.g., `my-service-account@...iam.gserviceaccount.com`) as an **Editor**.

#### ✉️ Part 2: Gmail API (OAuth2 Client)
Gmail requires OAuth2 because it sends emails on behalf of a real user.
1. In the Google Cloud Console, enable the **Gmail API**.
2. Go to **OAuth consent screen**:
   - Set User Type to **External**.
   - Complete the app name/contact details.
   - **Publish the App** (crucial, otherwise authorization tokens expire quickly).
3. Go to **Credentials → Create Credentials → OAuth client ID**.
   - Select **Desktop app** as application type.
   - Click **Create**, then click **Download JSON**.
   - Rename the downloaded file to `gmail_client_secret.json` and place it in the project root (`c:\git\emailcampaigntracker\`).
4. Run the one-time authentication script to generate your user token:
   ```powershell
   python generate_gmail_token.py
   ```
   - This opens a browser window. Log in to your target sender Gmail account, click **Allow**, and close the browser.
   - This creates `gmail_token.json` in your project root.

---

### Step C: Configure your `.env` File
Create a `.env` file in the project root. Populate it with the credentials from the service account JSON and your settings:

```env
# Google Sheets Service Account Credentials
GOOGLE_TYPE=service_account
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_PRIVATE_KEY_ID=your-private-key-id
GOOGLE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQD...==\n-----END PRIVATE KEY-----\n"
GOOGLE_CLIENT_EMAIL=your-service-account-email@your-project-id.iam.gserviceaccount.com
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
GOOGLE_TOKEN_URI=https://oauth2.googleapis.com/token
GOOGLE_AUTH_PROVIDER_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
GOOGLE_CLIENT_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/...
GOOGLE_UNIVERSE_DOMAIN=googleapis.com

# Target Google Sheet ID
GOOGLE_SHEET_ID=your-google-sheet-id-from-url
GOOGLE_SHEET_RANGE=Profiles!A1:Z

# Gemini AI Configuration
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-flash-lite-latest

# Gmail OAuth Token Path
GMAIL_OAUTH_CREDENTIALS_PATH=C:\git\emailcampaigntracker\gmail_token.json

# Local App Database URL (For Docker mapping)
DATABASE_URL=postgresql://postgres:121205@localhost:5432/drip_campaign
REDIS_URL=redis://localhost:6379/0

# Port & Internal Routing Configuration
APP_ENV=development
LOG_LEVEL=INFO
LOG_JSON=false
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:8080,http://127.0.0.1:5173
API_KEY=admin-key-123
DASHBOARD_API_KEY=dashboard-key-456
SCRAPER_API_KEY=scraper-key-789
JWT_SECRET_KEY=dev-jwt-secret
JWT_REFRESH_SECRET_KEY=dev-jwt-refresh-secret
TRACKING_SIGNING_SECRET=dev-tracking-signing-secret
REQUIRE_SIGNED_TRACKING=false

# Worker Settings
SCRAPER_QUEUE_NAME=scraper
CHROME_PROFILE_BASE_PATH=C:\selenium-profile\Default
LINKEDIN_PROFILE_NAME=Default
HEADLESS=false

# Tracking URLs (Dynamic Tunnel Url - See Section 4)
LOCAL_BACKEND_URL=https://placeholder.untun.com
```

> [!WARNING]
> The `GOOGLE_PRIVATE_KEY` must remain on **one single line** in the `.env` file, with literal `\n` characters replacing line breaks.

---

## ⚡ 4. How Tracking Works (Tracking Clicks & Opens)

For email open/click tracking to work, the tracking links embedded in outreach emails must be publicly accessible on the internet. Since you are developing locally, you must run a tunnel (`untun`) and configure your system to use it.

### 🚫 The "Port 8001" and "localhost" Pitfall
- **The Pitfall**: Running untun on port `8001` (e.g., `untun 8001`) while the main backend runs on port `8000` causes tracking to fail because requests are forwarded to a port where nothing is listening.
- **The Localhost Pitfall**: Using `localhost` or internal container names (like `api:8000`) in sent emails means the email recipient's client (e.g., Gmail, Outlook) cannot resolve the address, and tracking fails.
- **The Correct Setup**:
  1. Always run untun pointing to port **`8000`** (the FastAPI port):
     ```bash
     npx untun@latest tunnel http://localhost:8000
     ```
  2. Copy the public URL generated by untun (e.g., `https://funny-cats.untun.com`).
  3. Paste this URL into your `.env` file as **`LOCAL_BACKEND_URL`** before starting Docker or sending any emails:
     ```env
     LOCAL_BACKEND_URL=https://funny-cats.untun.com
     ```
  4. Now, any email sent will have its tracking pixel and redirects point to `https://funny-cats.untun.com/api/tracking/...`, allowing external clicks and opens to resolve to your local backend!

---

## 🗓️ 5. Daily Startup Routine (Running the System)

Follow these steps in order every time you start work:

### Step 1: Start the Public Tunnel
1. Open a new terminal on your Windows machine.
2. Start the tunnel:
   ```bash
   npx untun@latest tunnel http://localhost:8000
   ```
3. Copy the output URL (e.g., `https://random-word.untun.com`).

### Step 2: Update `.env`
1. Open your `.env` file.
2. Update the `LOCAL_BACKEND_URL` variable with the copied URL:
   ```env
   LOCAL_BACKEND_URL=https://random-word.untun.com
   ```
3. Save the `.env` file.

### Step 3: Refresh LinkedIn Cookies
LinkedIn session cookies expire frequently. Export active cookies from your local Chrome browser:
1. Open a new terminal and go to the project directory.
2. Activate your virtual environment and run:
   ```bash
   python export_cookies.py
   ```
3. A Chrome window opens. Log in to LinkedIn manually if prompted, solve any CAPTCHAs, and close the browser. The script will save `cookies.json` to the root folder.

### Step 4: Run the Docker Services
1. Start the Docker database, cache, backend, and dashboard services:
   ```bash
   docker compose up --build
   ```
2. Verify in the logs that `Workflow 3 follow-up scheduler started` and `Workflow 4 Gmail reply detection thread started` boot without errors.

### Step 5: Start the Scraper Worker
Since the scraper requires a local Chrome instance with access to the host session cookies, run the worker on the Windows host:
1. Open a new terminal.
2. Go to the project root, activate your virtual environment, and run:
   ```bash
   python -m app.workers.scraper_worker
   ```
3. The worker is now listening to Redis and ready to scrape.

---

## 📺 6. Running a Campaign & Verification

1. Go to the dashboard: **[http://localhost:5173](http://localhost:5173)**.
2. Click **Start Scraper** to trigger a scrape.
3. The worker scrapes URLs from the Google Sheet and returns them to the backend webhook.
4. The backend processes the leads (Workflow 1), personalizes emails via Gemini, and sends them via Gmail (Workflow 2).
5. **Verify tracking**:
   - Send a test email.
   - Open the email or click a link inside it.
   - Refresh the dashboard and verify that the lead's status changes to `OPENED` or `CLICKED`.

---

## 🛠️ 7. Maintenance & Troubleshooting

| Problem | Potential Cause | Action to Resolve |
| :--- | :--- | :--- |
| **"Authentication required" in worker logs** | LinkedIn cookies expired or CAPTCHA triggered. | Stop Docker, run `python export_cookies.py`, log in manually, then restart. |
| **Emails sent but clicks/opens aren't tracking** | `LOCAL_BACKEND_URL` is incorrect or untun is on the wrong port. | Run `untun 8000` and ensure the public URL is saved as `LOCAL_BACKEND_URL` in `.env`. |
| **Scraper worker won't pick up jobs** | Worker is not running or Redis URL mismatch. | Ensure `python -m app.workers.scraper_worker` is running in a terminal on the Windows host. |
| **Duplicate leads in database** | Manual/external edits inserted bypass. | Run the cleanup script on the host: `python scratch/db_cleanup.py`. |
