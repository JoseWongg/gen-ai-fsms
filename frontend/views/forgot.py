import streamlit as st
from shared import api_request

def show():
    st.title("Reset your password")
    with st.form("forgot_form"):
        email = st.text_input("Your email address")
        submitted = st.form_submit_button("Send reset link")
        if submitted:
            if not email.strip():
                st.error("Email is required.")
            else:
                resp = api_request("POST", "/auth/forgot-password", json={"email": email.strip()})
                if resp and resp.status_code == 200:
                    st.success("If the email exists, you will receive a reset link.")
                else:
                    st.error("Something went wrong. Please try again.")
    if st.button("Back to login"):
        st.session_state.page = "login"
        st.rerun()
