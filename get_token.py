import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zoho_proxy.settings')
django.setup()

from base.models import ZohoAccount
from base.views import get_valid_token

def get_latest_token():
    try:
        account = ZohoAccount.objects.filter(is_primary=True).first() or ZohoAccount.objects.first()
        
        if account:
            token = get_valid_token(account)
            print(f"Token: {token}")
            print(f"Domain: {account.api_domain}")
        else:
            print("No account found.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_latest_token()
