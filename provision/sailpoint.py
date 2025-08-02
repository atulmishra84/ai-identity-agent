import requests
import logging
from config.settings import SAILPOINT_API_KEY

def push_to_sailpoint(user):
    try:
        url = "https://your-sailpoint-instance.com/api/v3/users"
        headers = {
            "Authorization": f"Bearer {SAILPOINT_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "name": user["name"],
            "email": user["email"],
            "displayName": user["name"],
            "externalId": user.get("employee_id", user["email"]),
            "attributes": {
                "jobTitle": user.get("title"),
                "department": user.get("department"),
                "location": user.get("location"),
                "costcenter": user.get("costcenter")
            }
        }
        response = requests.post(url, headers=headers, json=payload)
        return response.status_code, response.json()
    except Exception as e:
        logging.error(f"SailPoint API error: {str(e)}")
        return 500, {"error": str(e)}