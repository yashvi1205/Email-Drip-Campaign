# AI Drip Campaign - Setup & Running Guide

This guide explains how to start and configure the full LinkedIn Scraper and Email Drip Campaign system locally.

## 1. Prerequisites
- **Python 3.10+**
- **Node.js & npm**
- **PostgreSQL** (Running locally or on Render)
- **Google Cloud Console** (for Sheets API and Gmail API)
- **ngrok** (to expose local backend to the internet for tracking pixels)

---

## 2. Environment Configuration
Create a `.env` file in the root directory with the following variables:

```env
# Backend & DB
DATABASE_URL=your_postgres_url
SECRET_KEY=your_random_secret_key

# Google Credentials (for Sheets & Gmail)
GOOGLE_TYPE=service_account
GOOGLE_PROJECT_ID=...
GOOGLE_PRIVATE_KEY=...
GOOGLE_CLIENT_EMAIL=...
# ... other google fields ...

# External URLs (Crucial for Tracking)
LOCAL_BACKEND_URL=https://your-ngrok-id.ngrok-free.app
RENDER_BACKEND_URL=https://your-app-name.onrender.com
```

---

## 3. Starting the Backend
From the root directory:
```powershell
# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn api.main:app --reload --port 8001
```
The API will be available at `http://localhost:8001`.

---

## 4. Starting the Frontend
Open a new terminal and navigate to the frontend folder:
```powershell
cd frontend
npm install
npm run dev
```
The Dashboard will be available at `http://localhost:5173`.

---

## 5. Setting up the Public Tunnel (Tracking Pixels)
Because email tracking pixels and n8n need to talk to your local backend, you must use **ngrok**:

1.  Start ngrok: `ngrok http 8001`
2.  Copy the Forwarding URL (e.g., `https://a1b2-c3d4.ngrok-free.app`).
3.  **UPDATE YOUR .ENV**: Set `LOCAL_BACKEND_URL` to this new ngrok URL.
4.  **UPDATE n8n**: In your n8n workflow, ensure any HTTP nodes pointing to your backend use this ngrok URL if they are running outside your local machine.

---

## 6. Updating Render (If using Hybrid Mode)
If you have a production version running on Render:
1.  Go to **Render Dashboard** -> Environment.
2.  Update `LOCAL_BACKEND_URL` in Render to match your current ngrok URL.
3.  This allows the Render "Public" server to forward tracking events (Opens/Clicks) to your local "Worker" machine.

---

## 7. Running the Scraper
- **Manually**: Click "Run Scraper Now" in the Drip Dashboard UI.
- **Automatically**: The n8n workflow "Phase1 Cron" is set to trigger every 2 hours.

### Important Notes:
- **Cookies**: The scraper handles session cookies automatically. If LinkedIn asks for a login, ensure your `profiles.txt` and `.env` are set correctly.
- **Deduplication**: The system only sends leads to n8n if **new activity** is detected on their profile. This prevents duplicate emails.
