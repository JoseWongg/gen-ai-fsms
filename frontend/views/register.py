import re

import streamlit as st

from shared import api_request, validate_password_strength


def is_valid_email(email):
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None


def show():
    st.title("Create an account")

    with st.form("register_form"):
        business_name = st.text_input("Business name *")
        site_name = st.text_input("Site/Venue name *")
        email = st.text_input("Email *")
        first = st.text_input("First name *")
        last = st.text_input("Last name *")
        password = st.text_input("Password *", type="password")

        st.caption(
            "Password must be at least 8 characters, include uppercase, "
            "lowercase, and a special character."
        )

        submitted = st.form_submit_button("Register")

        if submitted:
            business_name_val = business_name.strip()
            site_name_val = site_name.strip()
            email_val = email.strip()
            password_val = password.strip()
            first_val = first.strip()
            last_val = last.strip()

            if not business_name_val:
                st.error("Business name is required.")
            elif not site_name_val:
                st.error("Site/Venue name is required.")
            elif not email_val:
                st.error("Email is required.")
            elif not first_val:
                st.error("First name is required.")
            elif not last_val:
                st.error("Last name is required.")
            elif not password_val:
                st.error("Password is required.")
            elif not is_valid_email(email_val):
                st.error("Please enter a valid email address, for example name@example.com.")
            else:
                valid, msg = validate_password_strength(password_val)

                if not valid:
                    st.error(msg)
                else:
                    resp = api_request(
                        "POST",
                        "/auth/register",
                        json={
                            "business_name": business_name_val,
                            "site_name": site_name_val,
                            "email": email_val,
                            "password": password_val,
                            "first_name": first_val,
                            "last_name": last_val,
                        },
                    )

                    if resp is None:
                        st.error("Connection error. Please make sure the backend is running.")
                    elif resp.status_code == 201:
                        st.success("Account created! Please login.")
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        try:
                            detail = resp.json().get(
                                "detail",
                                f"Registration failed (HTTP {resp.status_code})",
                            )
                            st.error(detail)
                        except Exception:
                            st.error(f"Registration failed (HTTP {resp.status_code})")

    if st.button("Go Back"):
        st.session_state.page = "dashboard"
        st.rerun()
