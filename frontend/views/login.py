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
                    screening_state_keys = (
                        "screening_session",
                        "screening_messages",
                        "screening_complete",
                        "screening_just_completed",
                        "screening_processing",
                        "pending_screening_answer",
                        "screening_ephemeral_status",
                        "screening_ephemeral_after_index",
                        "screening_chat_input",
                    )

                    for key in screening_state_keys:
                        st.session_state.pop(key, None)

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
                except (ValueError, AttributeError):
                    # resp.json() could raise ValueError/JSONDecodeError or the parsed
                    # response might not be a dict (AttributeError on .get)
                    st.error(f"Login failed (HTTP {resp.status_code})")


    col_left, col_right = st.columns(2)
    with col_left:
        if st.button("Go Back", width='stretch'):
            st.session_state.page = "landing"
            st.rerun()
    with col_right:
        if st.button("Forgot password?", width='stretch'):
            st.session_state.page = "forgot"
            st.rerun()
