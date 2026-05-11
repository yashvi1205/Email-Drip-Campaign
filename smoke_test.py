import requests
import os
from dotenv import load_dotenv

# Load config
load_dotenv()

BASE_URL = os.getenv("BACKEND_INTERNAL_URL", "http://localhost:8001").rstrip("/")
API_KEY = os.getenv("DASHBOARD_API_KEY", os.getenv("API_KEY", "admin-key-123"))

print(f"🚀 Starting Smoke Tests on {BASE_URL}...")

def test_health():
    try:
        resp = requests.get(f"{BASE_URL}/api/health")
        if resp.status_code == 200:
            print("✅ Health Endpoint: PASS")
        else:
            print(f"❌ Health Endpoint: FAIL ({resp.status_code})")
    except Exception as e:
        print(f"❌ Health Endpoint: ERROR ({e})")

def test_dashboard():
    try:
        headers = {"X-API-Key": API_KEY}
        resp = requests.get(f"{BASE_URL}/api/dashboard/drip", headers=headers)
        if resp.status_code == 200:
            print("✅ Dashboard API (Auth): PASS")
        elif resp.status_code == 401:
            print("❌ Dashboard API (Auth): FAIL (Unauthorized - check API_KEY)")
        else:
            print(f"❌ Dashboard API (Auth): FAIL ({resp.status_code})")
    except Exception as e:
        print(f"❌ Dashboard API (Auth): ERROR ({e})")

def test_tracking():
    try:
        # Mock tracking request
        resp = requests.get(f"{BASE_URL}/api/tracking/open/smoke_test_id")
        if resp.status_code == 200:
            print("✅ Tracking Endpoint: PASS")
        else:
            print(f"❌ Tracking Endpoint: FAIL ({resp.status_code})")
    except Exception as e:
        print(f"❌ Tracking Endpoint: ERROR ({e})")

if __name__ == "__main__":
    test_health()
    test_dashboard()
    test_tracking()
    print("\n🏁 Smoke Tests Finished.")
