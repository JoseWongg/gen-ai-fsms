import streamlit as st

from shared import api_request


def show():
    st.title("Food Safety Management System Builder")
    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("You must be an admin to access the Food Safety Management System Builder.")
        return

    token = st.session_state.get("token")

    def load_readiness():
        response = api_request(
            "GET",
            "/onboarding/safety-points/readiness",
            token=token,
        )

        if response is None:
            st.error("Could not check whether the Food Safety Profile screening is complete.")
            return None

        if response.status_code != 200:
            st.error(f"Failed to check screening status (HTTP {response.status_code}).")
            return None

        return response.json()

    def load_current_approval_session():
        response = api_request(
            "GET",
            "/onboarding/safety-points/current",
            token=token,
        )

        if response is None:
            return None

        if response.status_code == 200:
            return response.json()

        if response.status_code == 404:
            return None

        st.error(f"Failed to load approval session (HTTP {response.status_code}).")
        return None

    def start_or_resume_approval():
        response = api_request(
            "POST",
            "/onboarding/safety-points/start",
            token=token,
        )

        if response and response.status_code == 200:
            return response.json()

        st.error("Could not start or resume the safety point approval workflow.")
        return None

    def reset_approval():
        response = api_request(
            "POST",
            "/onboarding/safety-points/reset",
            token=token,
        )

        if not response or response.status_code != 200:
            st.error("Failed to reset the safety point approval workflow.")
            return

        st.session_state.approval_session = None
        st.session_state.approval_messages = []
        st.session_state.approval_processing = False
        st.session_state.pending_approval_message = None
        st.session_state.approval_ephemeral_status = None
        st.session_state.approval_ephemeral_after_index = None
        st.session_state.approval_just_completed = False
        st.rerun()

    def render_progress_indicator(approval_session):
        progress = approval_session.get("progress") or {}

        total_count = progress.get("total_count", 0) or 0
        approved_count = progress.get("approved_count", 0) or 0

        if total_count <= 0:
            return

        if approval_session.get("workflow_status") == "completed":
            st.progress(1.0)
            return

        progress_value = min(max(approved_count / total_count, 0), 1)
        st.progress(progress_value)

    def render_reference_list(title, references):
        if not references:
            return

        st.markdown(f"**{title}**")
        for reference in references:
            st.markdown(f"- {reference}")

    def render_safety_point_card(
        safety_point_view,
        expanded,
        key_suffix,
        intro_message=None,
    ):
        current_safety_point = safety_point_view or {}
        safety_point_id = current_safety_point.get("safety_point_id") or "Unknown"
        original_safety_point_text = (
            current_safety_point.get("original_safety_point_text")
            or current_safety_point.get("safety_point_text")
            or current_safety_point.get("text")
            or ""
        )
        safety_point_instruction = (
            current_safety_point.get("safety_point_instruction")
            or current_safety_point.get("instruction")
            or original_safety_point_text
        )
        safety_point_rationale = (
            current_safety_point.get("safety_point_rationale")
            or current_safety_point.get("rationale")
            or ""
        )

        with st.expander(f"Safety Point: {safety_point_id}", expanded=expanded):
            st.markdown(f"**Section:** {current_safety_point.get('section_name') or 'Not available'}")
            st.markdown(f"**Safe method:** {current_safety_point.get('safe_method_name') or 'Not available'}")

            clean_intro_message = " ".join(str(intro_message or "").split())

            if clean_intro_message:
                st.markdown("**Introduction**")
                st.info(clean_intro_message)

            if safety_point_rationale:
                st.markdown("**Why this matters**")
                st.text_area(
                    label="Why this matters",
                    value=safety_point_rationale,
                    height=120,
                    disabled=True,
                    label_visibility="collapsed",
                    key=f"approval_safety_point_rationale_{safety_point_id}_{key_suffix}",
                )

            st.markdown("**Rule to approve**")
            st.text_area(
                label="Rule to approve",
                value=safety_point_instruction,
                height=160,
                disabled=True,
                label_visibility="collapsed",
                key=f"approval_safety_point_instruction_{safety_point_id}_{key_suffix}",
            )

            provenance_references = current_safety_point.get("provenance_references", [])
            source_references = current_safety_point.get("source_references", [])
            additional_source_references = current_safety_point.get("additional_source_references", [])
            references_to_show = provenance_references or source_references

            if references_to_show or additional_source_references:
                with st.expander("Provenance", expanded=False):
                    render_reference_list("Source references", references_to_show)
                    render_reference_list("Additional source references", additional_source_references)

    def render_required_additional_question(approval_session):
        current_question = approval_session.get("current_additional_question")

        if not current_question:
            return

        st.warning(
            "This safety point requires additional information before approval can be recorded."
        )

        question_text = current_question.get(
            "question_text",
            "Please answer the required additional question.",
        )

        st.markdown(f"**Required additional question:** {question_text}")

    def render_context_panel():
        if st.session_state.get("approval_session") is None:
            st.info(
                "This process reviews the SFBB safety points that are relevant to the "
                "completed Food Safety Profile.\n\n"
                "The purpose is to confirm which standard SFBB safety points the "
                "business will follow.\n\n"
                "Approved safety points can be viewed in the Food Safety section as "
                "Approved Methods."
            )
            return

        st.info(
            "You will be presented, one at a time, with relevant safety points based "
            "on your Food Safety Profile.\n\n"
            "You can confirm whether the business adheres to the safety point.\n\n"
            "Alternatively, you can ask clarification questions.\n\n"
            "Some safety points will need you to respond to additional questions "
            "before final approval.\n\n"
            "Approved safety points are part of your Food Safety Policy and can be "
            "viewed in the Food Safety section as Approved Methods."
        )

    def render_messages():
        messages = st.session_state.get("approval_messages", [])
        approval_session = st.session_state.get("approval_session") or {}
        current_safety_point = approval_session.get("current_safety_point") or {}
        current_safety_point_id = current_safety_point.get("safety_point_id")

        for index, message in enumerate(messages):
            role = message.get("role", "assistant")
            content = message.get("content", "")
            message_type = message.get("message_type")
            safety_point_id = message.get("safety_point_id")

            if message_type == "safety_point_presented":
                safety_point_view = message.get("safety_point_view")
                if safety_point_view:
                    render_safety_point_card(
                        safety_point_view=safety_point_view,
                        expanded=safety_point_id == current_safety_point_id,
                        key_suffix=index,
                        intro_message=content,
                    )
                    continue

            if role == "user":
                st.chat_message("user").write(content)
            else:
                st.chat_message("assistant").write(content)

            if (
                st.session_state.get("approval_ephemeral_status")
                and st.session_state.get("approval_ephemeral_after_index") == index
            ):
                st.info(st.session_state.approval_ephemeral_status)

        if st.session_state.get("approval_processing", False):
            st.info("Processing your message...")

    def submit_approval_message():
        if (
            st.session_state.get("approval_processing", False)
            or st.session_state.get("pending_approval_message") is not None
        ):
            return

        submitted_message = st.session_state.get("approval_chat_input")

        if not submitted_message:
            return

        st.session_state.pending_approval_message = submitted_message
        st.session_state.approval_processing = True

        current_messages = list(st.session_state.get("approval_messages", []))
        current_messages.append({
            "role": "user",
            "content": submitted_message,
            "message_type": "user_message",
        })
        st.session_state.approval_messages = current_messages

    def process_pending_message():
        if (
            not st.session_state.get("approval_processing", False)
            or not st.session_state.get("pending_approval_message")
        ):
            return

        pending_message = st.session_state.pending_approval_message
        latest_user_message_index = len(st.session_state.approval_messages) - 1

        response = api_request(
            "POST",
            "/onboarding/safety-points/message",
            json={"message": pending_message},
            token=token,
        )

        st.session_state.pending_approval_message = None
        st.session_state.approval_processing = False

        if response and response.status_code == 200:
            approval_session = response.json()
            st.session_state.approval_session = approval_session
            st.session_state.approval_messages = approval_session.get(
                "approval_chat_history",
                [],
            )

            if approval_session.get("workflow_status") == "completed":
                st.session_state.approval_just_completed = True
        else:
            st.session_state.approval_ephemeral_status = (
                "Failed to process message. Check backend logs."
            )
            st.session_state.approval_ephemeral_after_index = latest_user_message_index

        st.rerun()

    if "approval_session" not in st.session_state:
        st.session_state.approval_session = None

    if "approval_messages" not in st.session_state:
        st.session_state.approval_messages = []

    if "approval_processing" not in st.session_state:
        st.session_state.approval_processing = False

    if "pending_approval_message" not in st.session_state:
        st.session_state.pending_approval_message = None

    if "approval_ephemeral_status" not in st.session_state:
        st.session_state.approval_ephemeral_status = None

    if "approval_ephemeral_after_index" not in st.session_state:
        st.session_state.approval_ephemeral_after_index = None

    if "approval_just_completed" not in st.session_state:
        st.session_state.approval_just_completed = False

    readiness = load_readiness()

    if not readiness:
        return

    if not readiness.get("is_ready"):
        st.warning(
            "Complete the Food Safety Profile screening before starting the "
            "Food Safety Management System Builder."
        )

        if st.button("Open Food Safety Profile"):
            st.session_state.pending_navigation_route = "compliance_food_safety_profile"
            st.session_state.pending_navigation_label = "Profile Builder"
            st.rerun()

        return

    current_session = load_current_approval_session()

    if current_session:
        st.session_state.approval_session = current_session
        st.session_state.approval_messages = current_session.get(
            "approval_chat_history",
            [],
        )

    approval_session = st.session_state.get("approval_session")

    if approval_session is None:
        render_context_panel()

        if st.button("Start"):
            new_session = start_or_resume_approval()

            if new_session:
                st.session_state.approval_session = new_session
                st.session_state.approval_messages = new_session.get(
                    "approval_chat_history",
                    [],
                )
                st.session_state.approval_processing = False
                st.session_state.pending_approval_message = None
                st.session_state.approval_ephemeral_status = None
                st.session_state.approval_ephemeral_after_index = None
                st.rerun()

        return

    render_context_panel()

    if approval_session.get("workflow_status") == "completed":
        st.success(
            "FSMS Builder completed.\n\n"
            "All relevant safety points have been approved.\n\n"
            "Approved safety points are part of your Food Safety Policy and can be "
            "viewed in the Food Safety section as Approved Methods."
        )

        st.markdown("---")
        render_messages()
        render_progress_indicator(approval_session)

        if st.button("Reset and start over"):
            reset_approval()

        return

    st.markdown("---")
    render_messages()
    render_progress_indicator(approval_session)

    if st.session_state.get("approval_just_completed"):
        st.session_state.approval_just_completed = False

    if st.session_state.get("approval_ephemeral_status"):
        st.session_state.approval_ephemeral_status = None
        st.session_state.approval_ephemeral_after_index = None

    st.chat_input(
        "Type your message here...",
        key="approval_chat_input",
        disabled=st.session_state.get("approval_processing", False),
        on_submit=submit_approval_message,
    )

    process_pending_message()

    if st.button("Reset and start over"):
        reset_approval()
