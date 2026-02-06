import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
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
                    
                    # Use the standard OAuth User Info endpoint
                    info_resp = requests.get("https://accounts.zoho.com/oauth/user/info", headers=headers)
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
    return render(request, 'base/index.html', {'accounts': accounts})

def zoho_login(request):
    auth_url = f"{settings.ZOHO_AUTH_URL}?scope={settings.ZOHO_SCOPES}&client_id={settings.ZOHO_CLIENT_ID}&response_type=code&access_type=offline&redirect_uri={settings.ZOHO_REDIRECT_URI}&prompt=consent"
    return redirect(auth_url)

def zoho_callback(request):
    code = request.GET.get('code')
    if not code:
        return JsonResponse({'error': 'No code provided'}, status=400)

    data = {
        'code': code,
        'client_id': settings.ZOHO_CLIENT_ID,
        'client_secret': settings.ZOHO_CLIENT_SECRET,
        'redirect_uri': settings.ZOHO_REDIRECT_URI,
        'grant_type': 'authorization_code'
    }

    response = requests.post(settings.ZOHO_TOKEN_URL, data=data)
    res_data = response.json()

    if 'access_token' in res_data:
        expiry = timezone.now() + timedelta(seconds=res_data.get('expires_in', 3600))
        # For simplicity, we create or update a single connection for now, 
        # or we could use account_id if provided by Zoho.
        # Zoho returns 'api_domain' in the token response.
        api_domain = res_data.get('api_domain', 'https://www.zohoapis.com')
        
        # Get Identity Info using the new token
        account_display_name = "Zoho Account"
        headers = {'Authorization': f'Zoho-oauthtoken {res_data["access_token"]}'}
        try:
            # Try the standard Identity endpoint
            info_resp = requests.get("https://accounts.zoho.com/oauth/user/info", headers=headers)
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
                'expiry_time': expiry,
                'is_active': True,
                'is_primary': is_primary
            }
        )
        return redirect('index')
    else:
        return JsonResponse(res_data, status=400)

def refresh_zoho_token(account):
    data = {
        'refresh_token': account.refresh_token,
        'client_id': settings.ZOHO_CLIENT_ID,
        'client_secret': settings.ZOHO_CLIENT_SECRET,
        'grant_type': 'refresh_token'
    }
    response = requests.post(settings.ZOHO_TOKEN_URL, data=data)
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
    
    for key in data_keys:
        if key not in existing_fields and "_" not in key: # Skip system fields or weird ones
            # Try to create field
            create_url = f"{account.api_domain}/crm/v2/settings/fields?module={module}"
            field_data = {
                "fields": [
                    {
                        "api_name": key,
                        "display_label": key.replace('_', ' ').title(),
                        "data_type": "text",
                        "length": 255
                    }
                ]
            }
            requests.post(create_url, headers=headers, json=field_data)

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
def proxy_lead(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    
    try:
        payload = json.loads(request.body)
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
    
    return JsonResponse({
        'account': account.account_name,
        'status': resp.status_code,
        'response': resp.json()
    })
