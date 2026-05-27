# This file contains shared functions and constants for the frontend of the Gen AI FSMs project.
# It includes the BACKEND_URL constant and the api_request function for making API calls to the backend.
# The BACKEND_URL is loaded from the .env file, and the api_request function handles GET and POST requests with optional authentication tokens.
import requests
import os
from dotenv import load_dotenv

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")

def api_request(method, endpoint, json=None, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{BACKEND_URL}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            resp = requests.post(url, json=json, headers=headers)
        elif method == "PATCH":
            resp = requests.patch(url, json=json, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        return resp
    except Exception as e:
        print(f"API error: {e}")
        return None
    


def validate_password_strength(password):
    import re
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'[^A-Za-z0-9]', password):
        return False, "Password must contain at least one special character (e.g., !@#$%&*)."
    return True, ""