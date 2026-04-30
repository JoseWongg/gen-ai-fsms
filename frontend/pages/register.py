import streamlit as st
from frontend.api_client import api_request

def show():
    st.title("Create an account")
    with st.form("register_form"):
        email = st.text_input("Email")
        first_name = st.text_input("First name")
        last_name = st.text_input("Last name")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Register")
        if submitted:
            # Basic length check (more validation can be added later)
            if len(password) < 8:
                st.error("Password must be at least 8 characters.")
            else:
                resp = api_request("POST", "/auth/register", json={
                    "email": email,
                    "password": password,
                    "first_name": first_name,
                    "last_name": last_name
                })
                if resp and resp.status_code == 201:
                    st.success("Account created! You can now log in.")
                    # Optionally switch to login page after a few seconds
                else:
                    error_detail = resp.json().get("detail", "Registration failed") if resp else "Connection error"
                    st.error(error_detail)
