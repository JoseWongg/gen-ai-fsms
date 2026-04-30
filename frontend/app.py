import streamlit as st
from views.login import show as login_page
from views.register import show as register_page
from views.dashboard import show as dashboard_page
from views.profile import show as profile_page
from views.admin import show as admin_page
from views.forgot import show as forgot_page

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
    col_spacer, col_btn1, col_btn2 = st.columns([4, 1, 1])
    with col_btn1:
        if st.button("Login", width='stretch'):
            st.session_state.page = "login"
            st.rerun()
    with col_btn2:
        if st.button("Register", width='stretch'):
            st.session_state.page = "register"
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    # Centered image
    col1, col_img, col2 = st.columns([1, 2, 1])
    with col_img:
        st.image("assets/images/landing_1.png", width='stretch', caption="")


    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="text-align: center;">
            <h1>Welcome to Gen-AI Food Safety Management</h1>
            <p style="font-size:1.2rem;">Your intelligent assistant for food safety compliance.</p>
        </div>
        """,
        unsafe_allow_html=True
    )

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
    elif st.session_state.page == "forgot":
        forgot_page()
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

