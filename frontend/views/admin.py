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

    status_filter = st.selectbox(
        "Show users",
        options=["Active users", "Inactive users", "All users"],
    )

    if status_filter == "Active users":
        filtered_users = [
            user for user in users
            if user.get("is_active")
        ]
    elif status_filter == "Inactive users":
        filtered_users = [
            user for user in users
            if not user.get("is_active")
        ]
    else:
        filtered_users = users

    display_users = [
        {
            "Name": " ".join(
                part
                for part in [user.get("first_name"), user.get("last_name")]
                if part
            ),
            "Email": user.get("email"),
            "Role": user.get("role"),
            "Status": "Active" if user.get("is_active") else "Inactive",
        }
        for user in filtered_users
    ]

    if display_users:
        st.dataframe(display_users, hide_index=True)
    else:
        st.info("No users match the selected status filter.")

    st.divider()
    st.subheader("Deactivate user")

    active_users_to_deactivate = [
        user for user in users
        if user.get("is_active")
        and user.get("id") != current_user.get("id")
    ]

    if not active_users_to_deactivate:
        st.info("There are no other active users available to deactivate.")
    else:
        deactivate_options = {
            f"{user.get('first_name', '')} {user.get('last_name', '')} "
            f"({user.get('email')}) - {user.get('role')}".strip(): user["id"]
            for user in active_users_to_deactivate
        }

        with st.form("deactivate_venue_user_form"):
            selected_active_user_label = st.selectbox(
                "Select active user",
                options=list(deactivate_options.keys()),
            )

            deactivate_submitted = st.form_submit_button("Deactivate user")

            if deactivate_submitted:
                target_user_id = deactivate_options[selected_active_user_label]

                deactivate_response = api_request(
                    "PATCH",
                    f"/admin/users/{target_user_id}/deactivate",
                    token=token,
                )

                if deactivate_response is None:
                    st.error("Could not connect to the backend.")
                elif deactivate_response.status_code == 200:
                    st.success("User deactivated successfully.")
                    st.rerun()
                else:
                    try:
                        detail = deactivate_response.json().get(
                            "detail",
                            f"Failed to deactivate user "
                            f"(HTTP {deactivate_response.status_code}).",
                        )
                        st.error(detail)
                    except (ValueError, AttributeError):
                        st.error(
                            f"Failed to deactivate user "
                            f"(HTTP {deactivate_response.status_code})."
                        )
    st.divider()
    st.subheader("Reactivate user")

    inactive_users_to_reactivate = [
        user for user in users
        if not user.get("is_active")
    ]

    if not inactive_users_to_reactivate:
        st.info("There are no inactive users available to reactivate.")
    else:
        reactivate_options = {
            f"{user.get('first_name', '')} {user.get('last_name', '')} "
            f"({user.get('email')}) - {user.get('role')}".strip(): user["id"]
            for user in inactive_users_to_reactivate
        }

        with st.form("reactivate_venue_user_form"):
            selected_inactive_user_label = st.selectbox(
                "Select inactive user",
                options=list(reactivate_options.keys()),
            )

            reactivate_submitted = st.form_submit_button("Reactivate user")

            if reactivate_submitted:
                target_user_id = reactivate_options[selected_inactive_user_label]

                reactivate_response = api_request(
                    "PATCH",
                    f"/admin/users/{target_user_id}/reactivate",
                    token=token,
                )

                if reactivate_response is None:
                    st.error("Could not connect to the backend.")
                elif reactivate_response.status_code == 200:
                    st.success("User reactivated successfully.")
                    st.rerun()
                else:
                    try:
                        detail = reactivate_response.json().get(
                            "detail",
                            f"Failed to reactivate user "
                            f"(HTTP {reactivate_response.status_code}).",
                        )
                        st.error(detail)
                    except (ValueError, AttributeError):
                        st.error(
                            f"Failed to reactivate user "
                            f"(HTTP {reactivate_response.status_code})."
                        )

    st.divider()
    st.subheader("Promote user to admin")

    standard_users = [
        user for user in users
        if user.get("role") == "user"
        and user.get("is_active")
    ]

    if not standard_users:
        st.info("There are no active standard users available to promote.")
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

