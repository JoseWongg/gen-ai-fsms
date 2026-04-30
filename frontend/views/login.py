import streamlit as st
from shared import api_request

def show():
    st.title("Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            resp = api_request("POST", "/auth/login", json={"email": email, "password": password})
            if resp is None:
                st.error("Cannot reach the backend. Make sure FastAPI is running on port 8001.")
            elif resp.status_code == 200:
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
                try:
                    error_data = resp.json()
                    if isinstance(error_data.get("detail"), list):
                        # Validation error from FastAPI
                        first_error = error_data["detail"][0]
                        msg = first_error.get("msg", "Invalid input")
                        st.error(msg)
                    else:
                        st.error(error_data.get("detail", f"Login failed (HTTP {resp.status_code})"))
                except:
                    st.error(f"Login failed (HTTP {resp.status_code})")
    if st.button("Forgot password?"):
        st.session_state.page = "forgot"
        st.rerun()
