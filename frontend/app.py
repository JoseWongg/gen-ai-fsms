import streamlit as st
from pages.login import show as login_page
from pages.register import show as register_page
from pages.dashboard import show as dashboard_page
from pages.profile import show as profile_page
from pages.admin import show as admin_page

# Initialise session state
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

def logout():
    st.session_state.token = None
    st.session_state.user = None
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
        dashboard_page()
    elif st.session_state.page == "profile":
        profile_page()
    elif st.session_state.page == "admin":
        admin_page()
    else:
        dashboard_page()
