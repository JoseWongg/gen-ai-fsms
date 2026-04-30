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
        else:
            raise ValueError
        return resp
    except Exception as e:
        print(f"API error: {e}")
        return None
