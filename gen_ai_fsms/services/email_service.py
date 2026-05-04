import os
import requests

def send_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Send a password reset email using Mailgun REST API.
    Returns True if successful, False otherwise.
    """
    api_key = os.getenv("MAILGUN_API_KEY")
    domain = os.getenv("MAILGUN_DOMAIN")
    from_email = f"noreply@{domain}"

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
                "text": f"""Hello,

You requested a password reset for your account.

Click the link below to reset your password:

{reset_link}

If you did not request this, please ignore this email.

This link will expire in 24 hours.
"""
            },
            timeout=10
        )
        if response.status_code == 200:
            print(f"Password reset email sent to {to_email}")
            return True
        else:
            print(f"Mailgun API error: {response.status_code} - {response.text}")
            return False
    except requests.exceptions.Timeout:
        print("Mailgun request timed out.")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Mailgun request failed: {e}")
        return False