import streamlit as st
from frontend.api_client import api_request

def show():
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
                    st.rerun()
                else:
                    st.error("Failed to load profile")
            else:
                st.error("Invalid email or password")
