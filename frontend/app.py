import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()  # Load .env file

# Backend URL – read from environment, default to localhost
API_BASE = os.getenv("BACKEND_URL", "http://localhost:8001")

# Session state
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "home"

def api_request(method, endpoint, json=None):
    headers = {"Authorization": f"Bearer {st.session_state.token}"} if st.session_state.token else {}
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            resp = requests.post(url, json=json, headers=headers)
        else:
            raise ValueError("Unsupported method")
        return resp
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def login():
    st.title("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = api_request("POST", "/auth/login", json={"email": email, "password": password})
            if resp and resp.status_code == 200:
                data = resp.json()
                st.session_state.token = data["access_token"]
                # Fetch user profile
                user_resp = api_request("GET", "/users/me")
                if user_resp and user_resp.status_code == 200:
                    st.session_state.user = user_resp.json()
                    st.rerun()
                else:
                    st.error("Failed to load profile")
            else:
                st.error("Invalid email or password")

    with st.expander("Create an account"):
        with st.form("register_form"):
            reg_email = st.text_input("Email")
            reg_first = st.text_input("First name")
            reg_last = st.text_input("Last name")
            reg_pass = st.text_input("Password", type="password")
            reg_submit = st.form_submit_button("Register")
            if reg_submit:
                resp = api_request("POST", "/auth/register", json={
                    "email": reg_email, "password": reg_pass,
                    "first_name": reg_first, "last_name": reg_last
                })
                if resp and resp.status_code == 201:
                    st.success("Account created! Please log in.")
                else:
                    st.error("Registration failed")

    with st.expander("Forgot password?"):
        with st.form("forgot_form"):
            forgot_email = st.text_input("Email")
            forgot_submit = st.form_submit_button("Send reset link")
            if forgot_submit:
                resp = api_request("POST", "/auth/forgot-password", json={"email": forgot_email})
                if resp:
                    st.success("If the email exists, a reset link has been sent.")

def logout():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.page = "home"
    st.rerun()

def show_profile():
    st.title("Your Profile")
    st.write(f"**Email:** {st.session_state.user['email']}")
    st.write(f"**Name:** {st.session_state.user.get('first_name', '')} {st.session_state.user.get('last_name', '')}")
    st.write(f"**Role:** {st.session_state.user['role']}")

def show_admin():
    st.title("Admin Panel (Work in Progress)")
    st.info("Admin features will appear here.")

def show_home():
    st.title("Dashboard")
    st.write("This is the main dashboard (work in progress).")

# Main app
if not st.session_state.token:
    login()
else:
    # Sidebar navigation
    st.sidebar.title("Navigation")
    st.sidebar.write(f"Logged in as: {st.session_state.user.get('first_name', st.session_state.user['email'])}")
    if st.sidebar.button("Home"):
        st.session_state.page = "home"
    if st.sidebar.button("Profile"):
        st.session_state.page = "profile"
    if st.session_state.user.get("role") == "admin":
        if st.sidebar.button("Admin"):
            st.session_state.page = "admin"
    if st.sidebar.button("Logout"):
        logout()

    # Page content
    if st.session_state.page == "profile":
        show_profile()
    elif st.session_state.page == "admin":
        show_admin()
    else:
        show_home()
