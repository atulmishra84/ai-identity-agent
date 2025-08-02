
import requests

from config.settings import ENTRA_CLIENT_ID, ENTRA_CLIENT_SECRET, ENTRA_TENANT_ID


def get_graph_token():
    url = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/oauth2/v2.0/token"
    data = {
        'client_id': ENTRA_CLIENT_ID,
        'scope': 'https://graph.microsoft.com/.default',
        'client_secret': ENTRA_CLIENT_SECRET,
        'grant_type': 'client_credentials'
    }
    r = requests.post(url, data=data)
    return r.json()['access_token']

def create_entra_user(user):
    token = get_graph_token()
    url = "https://graph.microsoft.com/v1.0/users"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "accountEnabled": True,
        "displayName": user["name"],
        "mailNickname": user["nickname"],
        "userPrincipalName": user["email"],
        "passwordProfile": {
            "forceChangePasswordNextSignIn": True,
            "password": user["temp_password"]
        }
    }
    r = requests.post(url, headers=headers, json=payload)
    return r.status_code, r.json()

