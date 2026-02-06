# Zoho Proxy API

This proxy allows you to push lead data to your Zoho CRM. It handles OAuth2 authentication, token refreshing, and **dynamic field creation** (if a field in your payload doesn't exist in Zoho, it will be automatically created).

## 🚀 Quick Start
1. **Install Dependencies**: `pip install requests django`
2. **Run Server**: `python manage.py runserver`
3. **Connect Account**: Visit `http://localhost:8000/` and link your Zoho account.
4. **Test the API**: Run `python test_api.py`

## 🧪 Testing the API
We have included a `test_api.py` script to verify the connection. 
```bash
python test_api.py
```
This script sends a sample payload with dynamic fields. You can watch your terminal logs to see the proxy detecting missing fields, creating them in Zoho, and then submitting the lead.

## 1. Connecting Zoho Accounts
1. Start the server: `python manage.py runserver`
2. Navigate to `http://localhost:8000/`
3. Click **"Connect New Zoho Account"**.
4. Authorize the application. The proxy will securely store your refresh tokens.
5. **Multiple Accounts:** You can connect as many Zoho accounts as you want. Each will be listed on the dashboard with the owner's name and email.

## 2. Primary Account Logic
The proxy does **not** broadcast data to all accounts. Instead:
- You select one account as the **Primary Account** from the dashboard.
- When you hit the proxy endpoint, the system only sends data to that specific primary account.
- You can switch the primary account at any time with a single click.

## 3. API Endpoint

### Create Lead
`POST /api/leads/`

**Description:** Pushes lead data to the selected **Primary Zoho Account**.

**Request Body (JSON):**
```json
{
    "Last_Name": "Doe",
    "First_Name": "John",
    "Email": "john.doe@example.com",
    "Company": "Example Inc",
    "Source": "Web Proxy",
    "Your_Custom_Field": "Some Value"
}
```

**Note on Dynamic Fields:**
If `Your_Custom_Field` does not exist in the Zoho Leads module, the proxy will:
1. Detect the missing field.
2. Call Zoho Metadata API to create a "Text" field with the name `Your_Custom_Field`.
3. Proceed to create the lead with all provided data.

**Response:**
```json
{
    "results": [
        {
            "account": "Main Account",
            "status": 201,
            "response": { ... }
        }
    ]
}
```

## 3. Configuration
The proxy is pre-configured with the following details:
- **Client ID:** `1000.CGNEDBLS2WESK7DJT8PYIRKEGU5NSF`
- **Redirect URI:** `http://localhost:8000/api/oauth/zoho/callback/`
- **Scopes:** Leads (Create/Read), Field Settings (Create/Read)
