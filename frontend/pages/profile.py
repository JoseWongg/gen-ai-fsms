import streamlit as st
from ..api_client import api_request

def show():
    st.title("Your Profile")
    user = st.session_state.user
    if not user:
        st.error("No user data found. Please log in again.")
        return
    st.write(f"**Email:** {user.get('email', 'N/A')}")
    st.write(f"**Name:** {user.get('first_name', '')} {user.get('last_name', '')}")
    st.write(f"**Role:** {user.get('role', 'user')}")
