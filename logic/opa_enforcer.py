import logging

import requests

from config.settings import OPA_URL


def enforce_policy(user_data):
    try:
        response = requests.post(OPA_URL, json={"input": user_data})
        return response.json().get("result", {})
    except Exception as e:
        logging.error(f"OPA policy enforcement failed: {str(e)}")
        return {"allow": False, "reason": "OPA policy check failed"}

