import streamlit as st

from shared import api_request


def show():
    st.title("Food Safety Management System Builder")

    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("You must be an admin to access the Food Safety Management System Builder.")
        return

    token = st.session_state.get("token")

    response = api_request(
        "GET",
        "/onboarding/safety-points/readiness",
        token=token,
    )

    if response is None:
        st.error("Could not check whether the Food Safety Profile screening is complete.")
        return

    if response.status_code == 404:
        st.warning(
            "Complete the Food Safety Profile screening before starting the "
            "Food Safety Management System Builder. Use the button below to open the screening page."
        )

        if st.button("Open Food Safety Profile"):
            st.session_state.pending_navigation_route = "compliance_food_safety_profile"
            st.session_state.pending_navigation_label = "Profile"
            st.rerun()

        return

    if response.status_code != 200:
        st.error(f"Failed to check screening status (HTTP {response.status_code}).")
        return

    screening_status = response.json()

    if not screening_status.get("is_ready"):
        st.warning(
            "Complete the Food Safety Profile screening before starting the "
            "Food Safety Management System Builder. Use the button below to open the screening page."
        )

        if st.button("Open Food Safety Profile"):
            st.session_state.pending_navigation_route = "compliance_food_safety_profile"
            st.session_state.pending_navigation_label = "Profile"
            st.rerun()

        return

    st.success("Your Food Safety Profile screening is complete.")
    st.info("Relevant safety points will be shown here for review and approval.")