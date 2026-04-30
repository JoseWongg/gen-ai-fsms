import streamlit as st
import re
from shared import api_request

def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password_strength(password):
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r'[^A-Za-z0-9]', password):
        return False, "Password must contain at least one special character (e.g., !@#$%&*)."
    return True, ""

def show():
    st.title("Create an account")
    with st.form("register_form"):
        email = st.text_input("Email *")
        first = st.text_input("First name *")
        last = st.text_input("Last name *")
        password = st.text_input("Password *", type="password")
        st.caption("Password must be at least 8 characters, include uppercase, lowercase, and a special character.")
        submitted = st.form_submit_button("Register")
        if submitted:
            email_val = email.strip()
            password_val = password.strip()
            first_val = first.strip()
            last_val = last.strip()
            if not email_val:
                st.error("Email is required.")
            elif not first_val:
                st.error("First name is required.")
            elif not last_val:
                st.error("Last name is required.")
            elif not password_val:
                st.error("Password is required.")
            elif not is_valid_email(email_val):
                st.error("Please enter a valid email address (e.g., name@example.com).")
            else:
                valid, msg = validate_password_strength(password_val)
                if not valid:
                    st.error(msg)
                else:
                    resp = api_request("POST", "/auth/register", json={
                        "email": email_val,
                        "password": password_val,
                        "first_name": first_val,
                        "last_name": last_val
                    })
                    if resp is None:
                        st.error("Connection error. Please make sure the backend is running.")
                    elif resp.status_code == 201:
                        st.success("Account created! Please login.")
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        try:
                            detail = resp.json().get("detail", f"Registration failed (HTTP {resp.status_code})")
                            st.error(detail)
                        except:
                            st.error(f"Registration failed (HTTP {resp.status_code})")

    # Add a button to go back to login
    if st.button("Go Back"):
        st.session_state.page = "dashboard"
        st.rerun()
