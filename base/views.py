import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from .models import ZohoAccount
import json

def index(request):
    accounts = ZohoAccount.objects.all()
    # Proactively try to refresh generic names
    for account in accounts:
        if account.account_name == "Zoho Account" or not account.account_name:
            token = get_valid_token(account)
            if token:
                try:
                    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
                    print(f"DEBUG: Fetching identity from Zoho Accounts")
                    
                    # Use the regional OAuth User Info endpoint
                    info_resp = requests.get(f"{account.accounts_server}/oauth/user/info", headers=headers)
                    print(f"DEBUG: Info API Status: {info_resp.status_code}")
                    
                    if info_resp.status_code == 200:
                        info_data = info_resp.json()
                        account.account_name = f"{info_data.get('Display_Name')} ({info_data.get('Email')})"
                        print(f"DEBUG: Found Identity: {account.account_name}")
                    else:
                        print(f"DEBUG: Info API failed. Trying CRM Org fallback.")
                        org_resp = requests.get(f"{account.api_domain}/crm/v2/org", headers=headers)
                        if org_resp.status_code == 200:
                            org_data = org_resp.json().get('org', [{}])[0]
                            account.account_name = org_data.get('company_name', 'Zoho Account')
                    
                    if account.account_name != "Zoho Account":
                        account.save()
                except Exception as e:
                    print(f"DEBUG: Exception: {e}")
    primary_account = ZohoAccount.objects.filter(is_active=True, is_primary=True).first()
    return render(request, 'base/index.html', {'accounts': accounts, 'primary_account': primary_account})

def zoho_login(request):
    auth_url = f"{settings.ZOHO_AUTH_URL}?scope={settings.ZOHO_SCOPES}&client_id={settings.ZOHO_CLIENT_ID}&response_type=code&access_type=offline&redirect_uri={settings.ZOHO_REDIRECT_URI}&prompt=consent"
    return redirect(auth_url)

def zoho_callback(request):
    code = request.GET.get('code')
    accounts_server = request.GET.get('accounts-server') or settings.ZOHO_TOKEN_URL.replace('/oauth/v2/token', '')
    
    if not code:
        return JsonResponse({'error': 'No code provided'}, status=400)

    token_url = f"{accounts_server}/oauth/v2/token"
    data = {
        'code': code,
        'client_id': settings.ZOHO_CLIENT_ID,
        'client_secret': settings.ZOHO_CLIENT_SECRET,
        'redirect_uri': settings.ZOHO_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }

    response = requests.post(token_url, data=data)
    res_data = response.json()

    if 'access_token' in res_data:
        expiry = timezone.now() + timedelta(seconds=res_data.get('expires_in', 3600))
        # Zoho returns 'api_domain' in the token response.
        api_domain = res_data.get('api_domain', 'https://www.zohoapis.com')
        
        # Get Identity Info using the new token
        account_display_name = "Zoho Account"
        headers = {'Authorization': f'Zoho-oauthtoken {res_data["access_token"]}'}
        try:
            # Try the regional Identity endpoint
            info_resp = requests.get(f"{accounts_server}/oauth/user/info", headers=headers)
            if info_resp.status_code == 200:
                info_data = info_resp.json()
                account_display_name = f"{info_data.get('Display_Name')} ({info_data.get('Email')})"
            else:
                # CRM Org fallback
                org_resp = requests.get(f"{api_domain}/crm/v2/org", headers=headers)
                if org_resp.status_code == 200:
                    org_data = org_resp.json().get('org', [{}])[0]
                    account_display_name = org_data.get('company_name', 'Zoho Account')
        except:
            pass

        # Set as primary if no primary exists
        is_primary = False
        if not ZohoAccount.objects.filter(is_primary=True).exists():
            is_primary = True

        account, created = ZohoAccount.objects.update_or_create(
            refresh_token=res_data['refresh_token'],
            defaults={
                'account_name': account_display_name,
                'access_token': res_data['access_token'],
                'api_domain': api_domain,
                'accounts_server': accounts_server,
                'expiry_time': expiry,
                'is_active': True,
                'is_primary': is_primary
            }
        )
        return redirect('index')
    else:
        return JsonResponse(res_data, status=400)

def refresh_zoho_token(account):
    token_url = f"{account.accounts_server}/oauth/v2/token"
    data = {
        'refresh_token': account.refresh_token,
        'client_id': settings.ZOHO_CLIENT_ID,
        'client_secret': settings.ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token'
    }
    response = requests.post(token_url, data=data)
    res_data = response.json()
    if 'access_token' in res_data:
        account.access_token = res_data['access_token']
        account.expiry_time = timezone.now() + timedelta(seconds=res_data.get('expires_in', 3600))
        account.save()
        return True
    return False

def get_valid_token(account):
    if account.expiry_time <= timezone.now():
        if not refresh_zoho_token(account):
            return None
    return account.access_token

def ensure_fields_exist(account, module, data_keys):
    token = get_valid_token(account)
    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
    
    # Get existing fields
    fields_url = f"{account.api_domain}/crm/v2/settings/fields?module={module}"
    resp = requests.get(fields_url, headers=headers)
    if resp.status_code != 200:
        return # Fallback or log error
    
    existing_fields = {field['api_name'] for field in resp.json().get('fields', [])}
    
    # List of system fields to never try to create
    system_base_fields = {'First_Name', 'Last_Name', 'Email', 'Company', 'Phone', 'Mobile', 'Lead_Source', 'Lead_Status', 'Industry', 'Website', 'Description'}

    for key in data_keys:
        # Check if it's a new field (not in system fields and not in existing Zoho fields)
        if key not in existing_fields and key not in system_base_fields:
            print(f"DEBUG: Field '{key}' not found in Zoho. Attempting to create...")
            # Try to create field
            create_url = f"{account.api_domain}/crm/v2/settings/fields?module={module}"
            
            # Prepare API Name: Zoho API names usually don't like multiple underscores or starting with numbers
            # But we'll try to use what's provided first.
            field_data = {
                "fields": [
                    {
                        "api_name": key,
                        "display_label": key.replace('_', ' ').title(),
                        "data_type": "text",
                        "field_label": key.replace('_', ' ').title(), # Some versions use field_label
                        "length": 255
                    }
                ]
            }
            create_resp = requests.post(create_url, headers=headers, json=field_data)
            print(f"DEBUG: Field creation response for '{key}': {create_resp.status_code} - {create_resp.text}")

def set_primary(request, pk):
    account = get_object_or_404(ZohoAccount, pk=pk)
    account.is_primary = True
    account.save()
    return redirect('index')

def delete_account(request, pk):
    account = get_object_or_404(ZohoAccount, pk=pk)
    was_primary = account.is_primary
    account.delete()
    
    # If we deleted the primary, set someone else as primary if possible
    if was_primary:
        next_account = ZohoAccount.objects.first()
        if next_account:
            next_account.is_primary = True
            next_account.save()
            
    return redirect('index')

@csrf_exempt
def update_account_config(request, pk):
    if request.method == 'POST':
        account = get_object_or_404(ZohoAccount, pk=pk)
        data = json.loads(request.body)
        account.tenant_id = data.get('tenant_id')
        account.bookings_service_id = data.get('bookings_service_id')
        account.bookings_staff_id = data.get('bookings_staff_id')
        account.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)

def get_bookings_metadata(request, pk):
    """Fetch all services and staff for this account with data-center awareness."""
    account = get_object_or_404(ZohoAccount, pk=pk)
    token = get_valid_token(account)
    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
    
    # Construct base URL from CRM domain (e.g., https://www.zohoapis.in -> https://www.zohoapis.in/bookings/v1/json/)
    base_domain = account.api_domain # Usually https://www.zohoapis.com or .in
    bookings_base = f"{base_domain}/bookings/v1/json"
    
    print(f"DEBUG: Fetching metadata from {bookings_base} for account {account.account_name}")
    
    try:
        # Fetch Services
        services_url = f"{bookings_base}/services"
        services_resp = requests.get(services_url, headers=headers)
        
        print(f"DEBUG: Services Resp [{services_resp.status_code}]: {services_resp.text[:200]}")
        
        # Corrected parsing based on observed response: response -> returnvalue -> data
        services_data = services_resp.json().get('response', {}).get('returnvalue', {})
        services = services_data.get('data', [])
        
        # Fetch Staff
        staff_url = f"{bookings_base}/staffs"
        staff_resp = requests.get(staff_url, headers=headers)
        
        # Corrected parsing based on observed response: response -> returnvalue -> data
        staff_data = staff_resp.json().get('response', {}).get('returnvalue', {})
        staff = staff_data.get('data', [])
        
        if services:
            print(f"DEBUG: First Service Keys: {list(services[0].keys())}")
        if staff:
            print(f"DEBUG: First Staff Keys: {list(staff[0].keys())}")
            
        print(f"DEBUG: Found {len(services)} services and {len(staff)} staff members.")
        
        # Try both common Zoho key formats
        processed_services = []
        for s in services:
            s_id = s.get('service_id') or s.get('id')
            s_name = s.get('service_name') or s.get('name') or s.get('display_name')
            if s_id and s_name:
                processed_services.append({'id': s_id, 'name': s_name})
        
        processed_staff = []
        for s in staff:
            st_id = s.get('staff_id') or s.get('id')
            st_name = s.get('staff_name') or s.get('name') or s.get('display_name')
            if st_id and st_name:
                processed_staff.append({'id': st_id, 'name': st_name})
        
        return JsonResponse({
            'services': processed_services,
            'staff': processed_staff
        })
    except Exception as e:
        print(f"ERROR: Metadata fetch failed: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def proxy_lead(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    try:
        payload = json.loads(request.body)
        print(f"DEBUG: Proxy Lead Payload Received: {payload}")
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    # Get the primary account
    account = ZohoAccount.objects.filter(is_active=True, is_primary=True).first()
    if not account:
        return JsonResponse({'error': 'No primary Zoho account connected'}, status=400)

    # Ensure mandatory Last_Name exists if missing
    if 'Last_Name' not in payload and 'last_name' not in payload:
        payload['Last_Name'] = 'Unknown' # Default for Zoho mandatory field
    
    # 1. Ensure fields exist
    ensure_fields_exist(account, 'Leads', payload.keys())
    
    # 2. Push Lead
    token = get_valid_token(account)
    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
    lead_url = f"{account.api_domain}/crm/v2/Leads"
    
    lead_data = {"data": [payload]}
    resp = requests.post(lead_url, headers=headers, json=lead_data)
    resp_json = resp.json()

    # Extract Lead ID if successful
    lead_id = None
    try:
        if resp.status_code in [200, 201]:
            data = resp_json.get('data', [])
            if data and data[0].get('status') == 'success':
                lead_id = data[0].get('details', {}).get('id')
    except:
        pass

    return JsonResponse({
        'lead_id': lead_id,
        'account': account.account_name,
        'status': resp.status_code,
        'response': resp_json
    })

@csrf_exempt
def get_lead(request):
    """
    Search for a lead by ID, Email, or Phone.
    """
    # Support both GET and POST for convenience
    params = request.GET if request.method == 'GET' else json.loads(request.body or '{}')
    
    tenant_id = params.get('tenant_id')
    if not tenant_id:
        account = ZohoAccount.objects.filter(is_active=True, is_primary=True).first()
    else:
        account = ZohoAccount.objects.filter(tenant_id=tenant_id, is_active=True).first()

    if not account:
        return JsonResponse({'error': 'Zoho account not found'}, status=400)

    token = get_valid_token(account)
    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
    
    lead_id = params.get('id')
    email = params.get('email')
    phone = params.get('phone')

    lead_data = None
    
    # 1. Fetch by ID
    if lead_id:
        url = f"{account.api_domain}/crm/v2/Leads/{lead_id}"
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            lead_data = resp.json().get('data', [None])[0]
    
    # 2. Search by Email or Phone if ID not found or not provided
    if not lead_data and (email or phone):
        criteria = []
        if email: criteria.append(f"(Email:equals:{email})")
        if phone: criteria.append(f"(Phone:equals:{phone})")
        
        # Combine criteria with OR if both provided
        final_criteria = criteria[0] if len(criteria) == 1 else f"({'OR'.join(criteria)})"
        
        search_url = f"{account.api_domain}/crm/v2/Leads/search"
        resp = requests.get(search_url, headers=headers, params={'criteria': final_criteria})
        
        if resp.status_code == 200:
            lead_data = resp.json().get('data', [None])[0]

    if lead_data:
        return JsonResponse({
            'status': 'success',
            'account': account.account_name,
            'data': lead_data
        })
    else:
        return JsonResponse({
            'status': 'not_found',
            'message': 'No lead found matching the provided criteria'
        }, status=404)

# --- Zoho Bookings Helpers ---

def format_date_for_zoho(date_obj):
    return date_obj.strftime("%d-%b-%Y")

def format_datetime_for_zoho(date_obj, time_24h):
    return f"{date_obj.strftime('%d-%b-%Y')} {time_24h}:00"

def get_available_slots(account, date_obj, service_id, staff_id):
    token = get_valid_token(account)
    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
    base_domain = account.api_domain
    url = f"{base_domain}/bookings/v1/json/availableslots"
    params = {
        "service_id": service_id,
        "staff_id": staff_id,
        "selected_date": format_date_for_zoho(date_obj)
    }
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json().get("response", {}).get("returnvalue", {})
        return data.get("data", [])
    return []

@csrf_exempt
def proxy_booking(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    try:
        payload = json.loads(request.body)
    except:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    tenant_id = payload.get('tenant_id')
    if not tenant_id:
        # Fallback to primary account if tenant_id not specified
        account = ZohoAccount.objects.filter(is_active=True, is_primary=True).first()
    else:
        account = ZohoAccount.objects.filter(tenant_id=tenant_id, is_active=True).first()

    if not account:
        return JsonResponse({'error': 'Zoho account not found for this tenant'}, status=400)

    service_id = payload.get('service_id') or account.bookings_service_id
    staff_id = payload.get('staff_id') or account.bookings_staff_id
    
    if not service_id or not staff_id:
        return JsonResponse({'error': 'Bookings Service ID or Staff ID not configured'}, status=400)

    date_str = payload.get('date') # Expected YYYY-MM-DD
    time_str = payload.get('time') # Expected HH:MM (24h)
    
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    except:
        return JsonResponse({'error': 'Invalid date format. Use YYYY-MM-DD'}, status=400)

    customer_name = payload.get('name')
    customer_email = payload.get('email')
    customer_phone = payload.get('phone')

    # 1. Try to book
    token = get_valid_token(account)
    headers = {'Authorization': f'Zoho-oauthtoken {token}'}
    
    base_domain = account.api_domain
    booking_url = f"{base_domain}/bookings/v1/json/appointment"
    
    from_time = format_datetime_for_zoho(date_obj, time_str)
    
    post_data = {
        "service_id": service_id,
        "staff_id": staff_id,
        "from_time": from_time,
        "customer_details": json.dumps({
            "name": customer_name,
            "email": customer_email,
            "phone_number": customer_phone
        })
    }
    
    resp = requests.post(booking_url, headers=headers, data=post_data)
    res_data = resp.json().get("response", {}).get("returnvalue", {})
    
    if res_data.get("booking_id"):
        return JsonResponse({
            'status': 'booking done',
            'booking_id': res_data.get("booking_id"),
            'details': res_data
        })
    
    # 2. If booking failed, fetch available slots
    print(f"DEBUG: Booking failed for {from_time}. Searching for alternative slots...")
    
    current_date = date_obj
    for i in range(7): # Check up to 7 days ahead
        slots = get_available_slots(account, current_date, service_id, staff_id)
        if slots:
            return JsonResponse({
                'status': 'slot unavailable',
                'message': f'The requested slot was taken. Here are available slots for {format_date_for_zoho(current_date)}',
                'date': current_date.strftime("%Y-%m-%d"),
                'available_slots': slots
            })
        current_date += timedelta(days=1)

    return JsonResponse({
        'status': 'error',
        'message': 'No available slots found in the next 7 days.',
        'zoho_error': res_data.get("message")
    }, status=400)
