import os
import requests

def send_reset_email(to_email: str, reset_link: str) -> bool:
    api_key = os.getenv("MAILGUN_API_KEY")
    domain = os.getenv("MAILGUN_DOMAIN")
    print(f"DEBUG: MAILGUN_API_KEY={api_key[:10] if api_key else None}...")
    print(f"DEBUG: MAILGUN_DOMAIN={domain}")
    from_email = f"noreply@{domain}" if domain else "noreply@example.com"

    if not api_key or not domain:
        print("Missing Mailgun API configuration.")
        return False

    try:
        response = requests.post(
            f"https://api.mailgun.net/v3/{domain}/messages",
            auth=("api", api_key),
            data={
                "from": from_email,
                "to": [to_email],
                "subject": "Reset your password",
                "text": f"Reset link: {reset_link}"
            },
            timeout=10
        )
        print(f"Mailgun response: {response.status_code} - {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Mailgun request failed: {e}")
        return False
