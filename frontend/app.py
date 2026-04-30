import streamlit as st
import requests
import os
from dotenv import load_dotenv

load_dotenv()
API_BASE = os.getenv("BACKEND_URL", "http://localhost:8001")

def api_request(method, endpoint, json=None, token=None):
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{API_BASE}{endpoint}"
    try:
        if method == "GET":
            resp = requests.get(url, headers=headers)
        elif method == "POST":
            resp = requests.post(url, json=json, headers=headers)
        else:
            raise ValueError
        return resp
    except Exception:
        return None

if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = "landing"

def landing():
    st.title("Welcome to Gen-AI Food Safety Management")
    st.write("Your intelligent assistant for food safety compliance.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Login"):
            st.session_state.page = "login"
            st.rerun()
    with col2:
        if st.button("Create Account"):
            st.session_state.page = "register"
            st.rerun()

def login_page():
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
                user_resp = api_request("GET", "/users/me", token=st.session_state.token)
                if user_resp and user_resp.status_code == 200:
                    st.session_state.user = user_resp.json()
                    st.session_state.authenticated = True
                    st.session_state.page = "dashboard"
                    st.rerun()
                else:
                    st.error("Failed to load profile")
            else:
                st.error("Invalid credentials")

def register_page():
    st.title("Create an account")
    with st.form("register_form"):
        email = st.text_input("Email")
        first = st.text_input("First name")
        last = st.text_input("Last name")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            if len(password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                resp = api_request("POST", "/auth/register", json={
                    "email": email, "password": password,
                    "first_name": first, "last_name": last
                })
                if resp and resp.status_code == 201:
                    st.success("Account created! Please login.")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    err = resp.json().get("detail", "Registration failed") if resp else "Connection error"
                    st.error(err)

def dashboard():
    st.title("Dashboard")
    st.write("Welcome to the main dashboard (work in progress).")

def profile():
    st.title("Your Profile")
    user = st.session_state.user
    if user:
        st.write(f"**Email:** {user['email']}")
        st.write(f"**Name:** {user.get('first_name', '')} {user.get('last_name', '')}")
        st.write(f"**Role:** {user.get('role', 'user')}")

def admin_page():
    st.title("Admin Panel")
    st.info("Admin features – work in progress.")

def logout():
    st.session_state.clear()
    st.session_state.authenticated = False
    st.session_state.page = "landing"
    st.rerun()

# Routing
if not st.session_state.authenticated:
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "register":
        register_page()
    else:
        landing()
else:
    st.sidebar.title("Navigation")
    st.sidebar.write(f"Logged in as: {st.session_state.user.get('first_name', st.session_state.user['email'])}")
    if st.sidebar.button("Home"):
        st.session_state.page = "dashboard"
        st.rerun()
    if st.sidebar.button("Profile"):
        st.session_state.page = "profile"
        st.rerun()
    if st.session_state.user.get("role") == "admin":
        if st.sidebar.button("Admin"):
            st.session_state.page = "admin"
            st.rerun()
    if st.sidebar.button("Logout"):
        logout()

    if st.session_state.page == "dashboard":
        dashboard()
    elif st.session_state.page == "profile":
        profile()
    elif st.session_state.page == "admin":
        admin_page()
    else:
        dashboard()
