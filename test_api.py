import requests
import json
import time

# Configuration
API_URL = "http://localhost:8000/api/leads/"

def test_upsert_flow():
    print("🚀 Starting Zoho Proxy Upsert Test...")
    
    # 1. TEST INITIAL CREATION
    payload_create = {
        "First_Name": "Smart",
        "Last_Name": "Tester",
        "Email": "smart_test@example.com",
        "Phone": "9876543210",
        "Company": "Initial Company",
        "Lead_Source": "Multi-Tenant Test"
    }

    print("\n📦 STEP 1: Creating a new lead...")
    res1 = send_request(payload_create)
    if res1:
        print(f"✅ Result: {res1.get('action')} - Lead ID: {res1.get('lead_id')}")

    # Small delay for Zoho processing
    time.sleep(1)

    # 2. TEST UPDATE (Using same Email, different Company)
    payload_update = {
        "Email": "smart_test@example.com",
        "Company": "UPDATED SUCCESSFULY",
        "Description": "This confirms the upsert logic works!"
    }

    print("\n📦 STEP 2: Updating existing lead (sending same email)...")
    res2 = send_request(payload_update)
    if res2:
        print(f"✅ Result: {res2.get('action')} - Lead ID: {res2.get('lead_id')}")
        if res2.get('action') == 'updated':
            print("🌟 SUCCESS: Lead was updated instead of duplicated!")
        else:
            print("⚠️ Note: action was not 'updated'. Check Zoho settings.")

def send_request(payload):
    try:
        response = requests.post(
            API_URL, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

if __name__ == "__main__":
    test_upsert_flow()
