import streamlit as st
from shared import api_request, validate_password_strength

def show():
    st.title("Reset your password")

    # Get token from URL query parameters
    query_params = st.query_params
    token = query_params.get("token", "")

    with st.form("reset_form"):
        if not token:
            token = st.text_input("Reset token (copy from server logs)")

        new_password = st.text_input("New password", type="password")
        confirm_password = st.text_input("Confirm password", type="password")
        submitted = st.form_submit_button("Reset password")

        if submitted:
            if not token:
                st.error("Token is required.")
            elif not new_password:
                st.error("New password is required.")
            elif new_password != confirm_password:
                st.error("Passwords do not match.")
            else:
                valid, msg = validate_password_strength(new_password)
                if not valid:
                    st.error(msg)
                else:
                    resp = api_request(
                        "POST", "/auth/reset-password",
                        json={"token": token, "new_password": new_password}
                    )
                    if resp is not None and resp.status_code == 200:
                        st.success("Password reset successful! You can now log in.")
                        st.query_params.clear()
                        st.session_state.page = "login"
                        st.rerun()
                    elif resp is not None:
                        try:
                            err = resp.json().get(
                                "detail",
                                f"Reset failed (HTTP {resp.status_code}).",
                            )
                        except (ValueError, AttributeError):
                            err = f"Reset failed (HTTP {resp.status_code})."

                        st.error(err)
                    else:
                        st.error("Connection error.")

    if st.button("Back to login"):
        st.query_params.clear()
        st.session_state.page = "login"
        st.rerun()