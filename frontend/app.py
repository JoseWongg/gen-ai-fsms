import streamlit as st
from api_client import api_request
from pages import login, register, dashboard, profile, admin

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
        if st.button("Login", use_container_width=True):
            st.session_state.page = "login"
            st.rerun()
    with col2:
        if st.button("Create Account", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()

def logout():
    st.session_state.token = None
    st.session_state.user = None
    st.session_state.authenticated = False
    st.session_state.page = "landing"
    st.rerun()

# Page routing
if not st.session_state.authenticated:
    if st.session_state.page == "login":
        login.show()
    elif st.session_state.page == "register":
        register.show()
    else:
        landing()
else:
    # Sidebar navigation
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

    # Page content
    if st.session_state.page == "dashboard":
        dashboard.show()
    elif st.session_state.page == "profile":
        profile.show()
    elif st.session_state.page == "admin":
        admin.show()
    else:
        dashboard.show()
