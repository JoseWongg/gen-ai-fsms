import streamlit as st

from shared import api_request, validate_password_strength

def show():
    st.title("Venue User Administration")

    current_user = st.session_state.get("user")
    if not current_user or current_user.get("role") != "admin":
        st.error("You must be an admin to access venue user administration.")
        return

    token = st.session_state.get("token")

    business_name = current_user.get("business_name")
    site_name = current_user.get("site_name")

    if business_name:
        st.write(f"Business: {business_name}")

    if site_name:
        st.write(f"Venue: {site_name}")

    response = api_request("GET", "/admin/users", token=token)

    if response is None:
        st.error("Could not connect to the backend.")
        return

    if response.status_code != 200:
        st.error(f"Failed to load venue users (HTTP {response.status_code}).")
        return

    users = response.json()

    st.subheader("Users in this venue")

    if not users:
        st.info("No users were found for this venue.")
        return

    display_users = [
        {
            "Name": " ".join(
                part
                for part in [user.get("first_name"), user.get("last_name")]
                if part
            ),
            "Email": user.get("email"),
            "Role": user.get("role"),
        }
        for user in users
    ]

    st.dataframe(display_users, hide_index=True)

    st.divider()
    st.subheader("Promote user to admin")

    standard_users = [
        user for user in users
        if user.get("role") == "user"
    ]

    if not standard_users:
        st.info("There are no standard users available to promote.")
    else:
        promote_options = {
            f"{user.get('first_name', '')} {user.get('last_name', '')} ({user.get('email')})".strip(): user["id"]
            for user in standard_users
        }

        with st.form("promote_venue_user_form"):
            selected_user_label = st.selectbox(
                "Select user",
                options=list(promote_options.keys()),
            )

            promote_submitted = st.form_submit_button("Promote to admin")

            if promote_submitted:
                target_user_id = promote_options[selected_user_label]

                promote_response = api_request(
                    "PATCH",
                    f"/admin/users/{target_user_id}/promote",
                    token=token,
                )

                if promote_response is None:
                    st.error("Could not connect to the backend.")
                elif promote_response.status_code == 200:
                    st.success("User promoted to admin successfully.")
                    st.rerun()
                else:
                    try:
                        detail = promote_response.json().get(
                            "detail",
                            f"Failed to promote user (HTTP {promote_response.status_code}).",
                        )
                        st.error(detail)
                    except (ValueError, AttributeError):
                        st.error(
                            f"Failed to promote user "
                            f"(HTTP {promote_response.status_code})."
                        )

    st.divider()
    st.subheader("Demote admin to standard user")

    demotable_admins = [
        user for user in users
        if user.get("role") == "admin"
        and user.get("id") != current_user.get("id")
    ]

    if not demotable_admins:
        st.info("There are no other admin users available to demote.")
    else:
        demote_options = {
            f"{user.get('first_name', '')} {user.get('last_name', '')} ({user.get('email')})".strip(): user["id"]
            for user in demotable_admins
        }

        with st.form("demote_venue_user_form"):
            selected_admin_label = st.selectbox(
                "Select admin",
                options=list(demote_options.keys()),
            )

            demote_submitted = st.form_submit_button("Demote to standard user")

            if demote_submitted:
                target_user_id = demote_options[selected_admin_label]

                demote_response = api_request(
                    "PATCH",
                    f"/admin/users/{target_user_id}/demote",
                    token=token,
                )

                if demote_response is None:
                    st.error("Could not connect to the backend.")
                elif demote_response.status_code == 200:
                    st.success("Admin demoted to standard user successfully.")
                    st.rerun()
                else:
                    try:
                        detail = demote_response.json().get(
                            "detail",
                            f"Failed to demote admin (HTTP {demote_response.status_code}).",
                        )
                        st.error(detail)
                    except (ValueError, AttributeError):
                        st.error(
                            f"Failed to demote admin "
                            f"(HTTP {demote_response.status_code})."
                        )

    st.divider()
    st.subheader("Create user")

    with st.form("create_venue_user_form"):
        email = st.text_input("Email *")
        first_name = st.text_input("First name *")
        last_name = st.text_input("Last name *")
        password = st.text_input("Password *", type="password")

        st.caption(
            "Password must be at least 8 characters, include uppercase, "
            "lowercase, and a special character."
        )

        submitted = st.form_submit_button("Create user")

        if submitted:
            email_value = email.strip()
            first_name_value = first_name.strip()
            last_name_value = last_name.strip()
            password_value = password.strip()

            if not email_value:
                st.error("Email is required.")
            elif not first_name_value:
                st.error("First name is required.")
            elif not last_name_value:
                st.error("Last name is required.")
            elif not password_value:
                st.error("Password is required.")
            else:
                valid, message = validate_password_strength(password_value)

                if not valid:
                    st.error(message)
                else:
                    create_response = api_request(
                        "POST",
                        "/admin/users",
                        json={
                            "email": email_value,
                            "password": password_value,
                            "first_name": first_name_value,
                            "last_name": last_name_value,
                        },
                        token=token,
                    )

                    if create_response is None:
                        st.error("Could not connect to the backend.")
                    elif create_response.status_code == 201:
                        st.success("User created successfully.")
                        st.rerun()
                    else:
                        try:
                            detail = create_response.json().get(
                                "detail",
                                f"Failed to create user (HTTP {create_response.status_code}).",
                            )
                            st.error(detail)
                        except (ValueError, AttributeError):
                            st.error(
                                f"Failed to create user "
                                f"(HTTP {create_response.status_code})."
                            )

