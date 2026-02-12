import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zoho_proxy.settings')
django.setup()

import requests
import json
from datetime import datetime

from get_token import get_valid_token

import subprocess
import re

# CONSTANTS
# Programmatically fetch token
try:
    print("Fetching token via subprocess...")
    result = subprocess.run(["python", "get_token.py"], capture_output=True, text=True)
    output = result.stdout
    # Parse token
    token_match = re.search(r"Token:\s*([a-zA-Z0-9\.]+)", output)
    if not token_match:
        print("Failed to parse token from get_token.py output:", output)
        exit(1)
    
    ACCESS_TOKEN = token_match.group(1).strip()
    print(f"Used Token: {ACCESS_TOKEN[:10]}...")
    
    # Parse domain if possible, default to .in
    domain_match = re.search(r"Domain:\s*(https://[^ \n]+)", output)
    API_DOMAIN = domain_match.group(1).strip() if domain_match else "https://www.zohoapis.in"

except Exception as e:
    print(f"Failed to fetch token: {e}")
    exit(1)

BOOKING_URL = f"{API_DOMAIN}/bookings/v1/json/appointment"

def format_datetime_for_zoho(date_str, time_str):
    # Parse date
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    
    # Parse time to 24h format
    time_obj = None
    for fmt in ["%H:%M", "%I:%M %p", "%I:%M%p"]:
        try:
            time_obj = datetime.strptime(time_str.strip(), fmt)
            break
        except ValueError:
            continue
            
    if not time_obj:
        raise ValueError("Invalid time format")

    # Format: dd-MMM-yyyy HH:mm:ss
    return f"{date_obj.strftime('%d-%b-%Y')} {time_obj.strftime('%H:%M')}:00"

def get_services():
    url = f"{API_DOMAIN}/bookings/v1/json/services"
    headers = {'Authorization': f'Zoho-oauthtoken {ACCESS_TOKEN}'}
    print(f"\n--- Fetching Services ---")
    try:
        resp = requests.get(url, headers=headers)
        print(f"GET {url} Status: {resp.status_code}")
        if resp.status_code == 200:
            return resp.json().get('response', {}).get('returnvalue', {}).get('data', [])
        else:
            print(resp.text)
    except Exception as e:
        print(f"Services fetch failed: {e}")
    return []

def get_fields(service_id, workspace_id=None):
    headers = {'Authorization': f'Zoho-oauthtoken {ACCESS_TOKEN}'}
    
    params = {"service_id": service_id}
    if workspace_id:
        params["workspace_id"] = workspace_id
    
    print(f"\n--- Fetching Fields for Service {service_id} Workspace {workspace_id} ---")

    try:
        # Try endpoints with workspace_id
        # 'getfields' and 'fields' failed. Trying 'getappointmentfields'.
        for endp in ["getfields", "fields", "getappointmentfields"]:
            u = f"{API_DOMAIN}/bookings/v1/json/{endp}"
            print(f"Trying GET {u} with params {params}")
            resp = requests.get(u, headers=headers, params=params)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                print(json.dumps(resp.json(), indent=2))
                return
            else:
                print(f"Error: {resp.text}")
            
    except Exception as e:
        print(f"Fields fetch failed: {e}")

def test_booking(service_id, staff_id):
    payload = {
        "date": "2026-02-14",
        "time": "10:30 AM",
        "name": "Integration Tester",
        "email": "integrator@demo.local",
        "phone": "+919876543210",
        "service_id": service_id,
        "staff_id": staff_id
    }

    try:
        from_time = format_datetime_for_zoho(payload['date'], payload['time'])
        print(f"Formatted Time: {from_time}")
    except Exception as e:
        print(f"Time parsing error: {e}")
        return

    # Construct Customer Details
    customer_info = {
        "name": payload['name'],
        "email": payload['email'],
        "phone_number": payload['phone'],
    }
    
    # REPLACE 'UDF_CHAR_X' WITH THE ID YOU FIND IN THE BROWSER INSPECTOR
    # From HTML: <input ... name="x_State" ...>
    # This suggests the ID is "State" or "x_State"
    
    # FOUND IT! Based on screenshot:
    # "407473000000047017": "TN"
    field_id = "407473000000047017" # The numeric ID for State
    
    # Mimic screenshot structure
    # additionalInfo is a nested JSON string or object inside customer_details
    # Screenshot shows: "additionalInfo": "{\"WORKSPACE_ID\":\"...\", ...}"
    
    workspace_id = "407473000000045076" # From screenshot
    field_id = "407473000000047017"     # State
    
    # Based on provided docs: "customer_more_info"
    # Also valid for some APIs: "customer_more_info": {"State": "TN"}
    
    # FINAL REQUEST FOR MANUAL VERIFICATION
    # We use the Numeric ID found in logs: 407473000000047017
    
    clean_dict = {
        "407473000000047017": "TN",
        "State": "TN"
    }
    
    customer_info["custom_fields"] = clean_dict
    customer_info["customer_more_info"] = clean_dict
    
    print("\n[IMPORTANT] Please UNCHECK 'Mandatory' for the 'State' field in Zoho Bookings -> Services -> Booking Form.")
    print("Then run this script. If booking succeeds, check if 'State' is populated in the booking details.")
    
    # Try additional_fields outside customer_details
    param_dict = {
        "State": "TN",
        "407473000000047017": "TN"
    }
    
    post_data = {
        "service_id": payload['service_id'],
        "staff_id": payload['staff_id'],
        "from_time": from_time,
        "customer_details": json.dumps(customer_info),
        "additional_fields": json.dumps(param_dict), # As JSON string
        "custom_fields": json.dumps(param_dict)      # As JSON string
    }

    headers = {
        'Authorization': f'Zoho-oauthtoken {ACCESS_TOKEN}'
    }

    print("\n--- Sending Request ---")
    print(f"URL: {BOOKING_URL}")
    print(f"Data Payload: {post_data}")

    try:
        response = requests.post(BOOKING_URL, headers=headers, data=post_data)
        print(f"\nResponse Status: {response.status_code}")
        try:
            print(f"Response Body: {json.dumps(response.json(), indent=2)}")
        except:
            print(f"Response Body: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    target_service_id = "407473000000047002"
    staff_id = "407473000000041016"
    test_booking(target_service_id, staff_id)
