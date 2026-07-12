import pandas as pd
import streamlit as st
from shared import api_request


def show():
    st.title("Onboarding – Screening Chatbot")

    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("You must be an admin to access onboarding.")
        return

    token = st.session_state.get("token")

    def load_current_session():
        resp = api_request("GET", "/onboarding/screening/current", token=token)

        if resp is None:
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 404:
            return None

        st.error(f"Failed to load session (HTTP {resp.status_code}). Please try again.")
        return None





    def load_condition_values():
        resp = api_request("GET", "/onboarding/screening/condition-values", token=token)

        if resp is None:
            return None

        if resp.status_code == 200:
            return resp.json()

        if resp.status_code == 404:
            return None

        st.error(f"Failed to load condition values (HTTP {resp.status_code}). Please try again.")
        return None


    def start_session():
        resp = api_request("POST", "/onboarding/screening/start", token=token)

        if resp and resp.status_code == 200:
            return resp.json()

        st.error("Could not start screening. Check backend logs.")
        return None

    def reset_screening():
        resp = api_request("POST", "/onboarding/screening/reset", token=token)
        if not resp or resp.status_code != 200:
            st.error("Failed to reset screening. Check backend logs.")
            return

        st.session_state.screening_session = None
        st.session_state.screening_messages = []
        st.session_state.screening_complete = False
        st.session_state.screening_just_completed = False
        st.session_state.screening_processing = False
        st.session_state.pending_screening_answer = None
        st.session_state.screening_ephemeral_status = None
        st.session_state.screening_ephemeral_after_index = None
        st.session_state.screening_reset_confirmation_requested = False
        st.session_state.screening_business_type_select = None

        st.session_state.approval_session = None
        st.session_state.approval_messages = []
        st.session_state.approval_processing = False
        st.session_state.pending_approval_message = None
        st.session_state.approval_ephemeral_status = None
        st.session_state.approval_ephemeral_after_index = None
        st.session_state.approval_just_completed = False

        st.rerun()

    def render_reset_screening_controls():
        if not st.session_state.screening_reset_confirmation_requested:
            if st.button("Reset and start over"):
                st.session_state.screening_reset_confirmation_requested = True
                st.rerun()
            return

        st.warning(
            "Resetting the Food Safety Profile will also reset the FSMS Builder "
            "workflow and remove the currently approved food safety methods for "
            "this business profile.\n\n"
            "This will also set existing fridge/chilling equipment records to "
            "inactive. If there is an active shift, its fridge temperature "
            "checklist will be cleared and will contain no chilling equipment "
            "until equipment is added again or reactivated.\n\n"
            "Any active-shift temperature incidents, corrective actions, and "
            "related notifications will also be deleted.\n\n"
            "This is because the approved methods, equipment setup, and "
            "active-shift temperature checks depend on the screening/profile "
            "answers."
        )

        col_confirm, col_cancel = st.columns(2)

        with col_confirm:
            if st.button("Confirm reset"):
                reset_screening()

        with col_cancel:
            if st.button("Cancel"):
                st.session_state.screening_reset_confirmation_requested = False
                st.rerun()

    def render_condition_values_table(condition_values):
        table = pd.DataFrame(condition_values)

        table = table[["condition_name", "value"]]
        table = table.rename(columns={
            "condition_name": "Condition Name",
            "value": "Value"
        })

        st.markdown(
            """
            <style>
            table.condition-values-table {
                width: 100%;
                border-collapse: collapse;
            }
            table.condition-values-table th,
            table.condition-values-table td {
                text-align: center !important;
                padding: 0.5rem;
                border-bottom: 1px solid rgba(49, 51, 63, 0.2);
            }
            table.condition-values-table th {
                font-weight: 600;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        html_table = table.to_html(
            index=False,
            escape=True,
            classes="condition-values-table"
        )

        st.markdown(html_table, unsafe_allow_html=True)

    def render_progress_indicator(condition_values_response):
        if not condition_values_response:
            return

        active_count = condition_values_response.get("active_condition_count", 0)
        completed_count = condition_values_response.get("completed_active_condition_count", 0)

        if active_count <= 0:
            return

        progress = completed_count / active_count
        st.progress(progress)


    if "screening_session" not in st.session_state:
        st.session_state.screening_session = None

    if "screening_messages" not in st.session_state:
        st.session_state.screening_messages = []

    if "screening_complete" not in st.session_state:
        st.session_state.screening_complete = False

    if "screening_just_completed" not in st.session_state:
        st.session_state.screening_just_completed = False

    if "screening_processing" not in st.session_state:
        st.session_state.screening_processing = False

    if "pending_screening_answer" not in st.session_state:
        st.session_state.pending_screening_answer = None

    if "screening_ephemeral_status" not in st.session_state:
        st.session_state.screening_ephemeral_status = None

    if "screening_ephemeral_after_index" not in st.session_state:
        st.session_state.screening_ephemeral_after_index = None
    if "screening_reset_confirmation_requested" not in st.session_state:
        st.session_state.screening_reset_confirmation_requested = False

    if "screening_business_type_select" not in st.session_state:
        st.session_state.screening_business_type_select = None

    current = load_current_session()
    condition_values_response = load_condition_values()

    if current:
        st.session_state.screening_session = current

        if not st.session_state.screening_messages:
            st.session_state.screening_messages = current.get(
                "display_messages",
                [
                    {
                        "role": "assistant",
                        "content": current["question_text"]
                    }
                ]
            )

    else:
        if condition_values_response and condition_values_response.get("is_complete"):
            if not st.session_state.get("screening_just_completed"):
                st.subheader("Completed screening profile")
                st.write(
                    "The screening process is complete. "
                    "The recorded condition values are shown below."
                )

                render_progress_indicator(condition_values_response)

                condition_values = condition_values_response.get("condition_values", [])

                if condition_values:
                    render_condition_values_table(condition_values)
                else:
                    st.info("No condition values were found.")

                render_reset_screening_controls()
                return

        else:
            st.info(
                "This process gathers business-specific information to determine the "
                "Food Safety Profile.\n\n"
                "The answers are used to identify the conditions that later control "
                "which relevant SFBB safety points are presented for assessment and approval."
            )

            if st.button("Start"):
                new_session = start_session()

                if new_session:
                    st.session_state.screening_complete = False
                    st.session_state.screening_just_completed = False
                    st.session_state.screening_processing = False
                    st.session_state.pending_screening_answer = None
                    st.session_state.screening_ephemeral_status = None
                    st.session_state.screening_ephemeral_after_index = None
                    st.session_state.screening_session = new_session
                    st.session_state.screening_messages = new_session.get(
                        "display_messages",
                        [
                            {
                                "role": "assistant",
                                "content": new_session["question_text"],
                            }
                        ],
                    )
                    st.session_state.screening_business_type_select = None
                    st.rerun()

            return

    # Display conversation and any one-time status message in the correct position.
    for index, msg in enumerate(st.session_state.screening_messages):
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        else:
            st.chat_message("assistant").write(msg["content"])

        if (
            st.session_state.get("screening_ephemeral_status")
            and st.session_state.get("screening_ephemeral_after_index") == index
        ):
            st.info(st.session_state.screening_ephemeral_status)

    # If a response is being processed, show the processing message directly
    # below the latest submitted user response.
    if st.session_state.get("screening_processing", False):
        st.info("Processing your response...")

    if st.session_state.get("screening_just_completed"):
        st.session_state.screening_just_completed = False

    # Ephemeral status is shown for one render only. 
    # Ephemeral status is used to show one-time messages that are directly relevant to the latest user response, such as errors or unexpected conditions. It is cleared on every render to ensure it does not persist longer than intended.
    if st.session_state.get("screening_ephemeral_status"):
        st.session_state.screening_ephemeral_status = None
        st.session_state.screening_ephemeral_after_index = None

    if current:
        render_progress_indicator(condition_values_response)

    def queue_screening_answer(submitted_answer):
        if (
            st.session_state.get("screening_complete", False)
            or st.session_state.get("screening_processing", False)
            or st.session_state.get("pending_screening_answer") is not None
        ):
            return

        if not submitted_answer:
            return

        st.session_state.screening_messages.append({
            "role": "user",
            "content": submitted_answer
        })

        st.session_state.pending_screening_answer = submitted_answer
        st.session_state.screening_processing = True

    def submit_screening_answer():
        submitted_answer = st.session_state.get("screening_chat_input")
        queue_screening_answer(submitted_answer)

    def render_business_type_input(current_session):
        options = current_session.get("question_options") or []
        labels_by_value = {
            option.get("value"): option.get("label")
            for option in options
        }

        option_values = [
            option.get("value")
            for option in options
            if option.get("value")
        ]

        selected_value = st.selectbox(
            "Business type",
            options=option_values,
            format_func=lambda value: labels_by_value.get(value, value),
            index=None,
            placeholder="Select the type of food business",
            key="screening_business_type_select",
            disabled=st.session_state.get("screening_processing", False),
        )

        if st.button(
            "Continue",
            use_container_width=True,
            disabled=(
                st.session_state.get("screening_processing", False)
                or selected_value is None
            ),
        ):
            queue_screening_answer(selected_value)
            st.rerun()

    current_session_for_input = st.session_state.get("screening_session") or {}
    question_input_type = current_session_for_input.get("question_input_type", "chat")

    if question_input_type == "select":
        render_business_type_input(current_session_for_input)
    else:
        is_business_description = question_input_type == "textarea"

        st.chat_input(
            (
                "Tell us about the business..."
                if is_business_description
                else "Type your answer here..."
            ),
            key="screening_chat_input",
            max_chars=500 if is_business_description else None,
            disabled=(
                st.session_state.get("screening_complete", False)
                or st.session_state.get("screening_processing", False)
            ),
            on_submit=submit_screening_answer,
        )

    if (
        st.session_state.get("screening_processing", False)
        and st.session_state.get("pending_screening_answer")
    ):
        pending_answer = st.session_state.pending_screening_answer
        latest_user_message_index = len(st.session_state.screening_messages) - 1

        resp = api_request(
            "POST",
            "/onboarding/screening/answer",
            json={"answer": pending_answer},
            token=token
        )

        st.session_state.pending_screening_answer = None
        st.session_state.screening_processing = False

        if resp and resp.status_code == 200:
            data = resp.json()
            action = data.get("action")
            message = data.get("message")

            if action == "next_question":
                if message:
                    st.session_state.screening_messages.append({
                        "role": "assistant",
                        "content": message
                    })

                question_text = data["question_text"]

                st.session_state.screening_messages.append({
                    "role": "assistant",
                    "content": question_text
                })

                st.session_state.screening_session["question_text"] = question_text
                st.session_state.screening_session["question_id"] = data["question_id"]
                st.session_state.screening_session["question_type"] = data.get(
                    "question_type",
                    "screening",
                )
                st.session_state.screening_session["question_input_type"] = data.get(
                    "question_input_type",
                    "chat",
                )
                st.session_state.screening_session["question_options"] = data.get(
                    "question_options",
                    [],
                )

            elif action == "ask_again":
                ask_again_message = data["message"]

                st.session_state.screening_messages.append({
                    "role": "assistant",
                    "content": ask_again_message
                })

            elif action == "complete":
                completion_message = (
                    "Screening completed.\n\n"
                    "Your responses have been recorded.\n\n"
                    "You will be able to view the recorded condition values when you visit this page again.\n\n"
                    "You can now continue to the Food Safety Management System Builder, where the relevant "
                    "safety points for your business will be reviewed and approved."
                )

                st.session_state.screening_messages.append({
                    "role": "assistant",
                    "content": completion_message
                })

                st.session_state.screening_complete = True
                st.session_state.screening_just_completed = True
                st.session_state.screening_session = None

            else:
                st.session_state.screening_ephemeral_status = "Unexpected response from server."
                st.session_state.screening_ephemeral_after_index = latest_user_message_index

        else:
            st.session_state.screening_ephemeral_status = "Failed to process answer. Check backend logs."
            st.session_state.screening_ephemeral_after_index = latest_user_message_index

        st.rerun()

    render_reset_screening_controls()