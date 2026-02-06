import requests
import json

# Configuration
API_URL = "http://localhost:8000/api/leads/"

def test_proxy_lead():
    print("🚀 Starting Zoho Proxy API Test...")
    
    # Sample Lead Data
    # Note: 'Last_Name' is mandatory in Zoho. 
    # Any field that doesn't exist in your Zoho CRM will be automatically created by the proxy.
    payload = {
        "First_Name": "Automated",
        "Last_Name": "Tester",
        "Email": "test_lead@example.com",
        "Company": "XtraCut Debugging",
        "Lead_Source": "Python Test Script",
        "Test_Custom_Field_1": "Dynamic Value 123",
        "Another_New_Field": "This should trigger auto-creation"
    }

    try:
        print(f"📡 Sending POST request to: {API_URL}")
        response = requests.post(
            API_URL, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success! Response Data:")
            print(json.dumps(response.json(), indent=4))
        else:
            print("❌ Failed! Error Details:")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the server. Make sure 'python manage.py runserver' is running!")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

if __name__ == "__main__":
    test_proxy_lead()
