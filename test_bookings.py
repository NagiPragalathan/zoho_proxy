import requests
import json
from datetime import datetime, timedelta

# Configuration
API_URL = "http://127.0.0.1:8000/api/bookings/"

def test_booking_logic():
    print("🚀 Starting Zoho Bookings Proxy Test...")
    
    # Use a future date for testing
    test_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    payload = {
        "date": test_date,
        "time": "14:30",
        "name": "Integration Tester",
        "email": "tester@example.com",
        "phone": "+919876543210",
        "service_id": "MOCK_SERVICE_ID", 
        "staff_id": "MOCK_STAFF_ID"
    }

    try:
        print(f"📡 Attempting to book for {test_date} at 14:30...")
        response = requests.post(
            API_URL, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        data = response.json()
        print(f"DEBUG: Full Response: {json.dumps(data, indent=2)}")
        print(f"📊 Status: {data.get('status')}")
        
        if data.get('status') == 'booking done':
            print(f"✅ Booking Confirmed! ID: {data.get('booking_id')}")
        elif data.get('status') == 'slot unavailable':
            print(f"⚠️ Slot taken. Alternatives found for {data.get('date')}:")
            print(f"🕒 {data.get('available_slots')}")
        else:
            print(f"❌ Error: {data.get('message')}")
            if 'zoho_error' in data:
                print(f"🔍 Zoho Error: {data['zoho_error']}")
            if not data.get('status') and not data.get('message'):
                print(f"🔍 Raw Data: {data}")

    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    test_booking_logic()
