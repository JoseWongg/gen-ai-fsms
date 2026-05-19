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

    #def load_condition_values():
        #resp = api_request("GET", "/onboarding/screening/condition-values", token=token)

        #if resp is None:
            #return None

        #if resp.status_code == 200:
            #return resp.json()

        #st.error(f"Failed to load condition values (HTTP {resp.status_code}). Please try again.")
        #return None







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

    current = load_current_session()
    condition_values_response = load_condition_values()

    if current:
        st.session_state.screening_session = current

        if not st.session_state.screening_messages:
            st.session_state.screening_messages.append({
                "role": "assistant",
                "content": current["question_text"]
            })

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

                if st.button("Reset and start over"):
                    reset_screening()

                return

        else:
            if st.button("Start onboarding"):
                new_session = start_session()

                if new_session:
                    st.session_state.screening_complete = False
                    st.session_state.screening_just_completed = False
                    st.session_state.screening_processing = False
                    st.session_state.pending_screening_answer = None
                    st.session_state.screening_ephemeral_status = None
                    st.session_state.screening_ephemeral_after_index = None
                    st.session_state.screening_session = new_session
                    st.session_state.screening_messages.append({
                        "role": "assistant",
                        "content": new_session["question_text"]
                    })
                    st.rerun()

            st.info("Click 'Start onboarding' to begin the screening process.")
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

    def submit_screening_answer():
        if (
            st.session_state.get("screening_complete", False)
            or st.session_state.get("screening_processing", False)
            or st.session_state.get("pending_screening_answer") is not None
        ):
            return

        submitted_answer = st.session_state.get("screening_chat_input")

        if not submitted_answer:
            return

        st.session_state.screening_messages.append({
            "role": "user",
            "content": submitted_answer
        })

        st.session_state.pending_screening_answer = submitted_answer
        st.session_state.screening_processing = True

    st.chat_input(
        "Type your answer here...",
        key="screening_chat_input",
        disabled=(
            st.session_state.get("screening_complete", False)
            or st.session_state.get("screening_processing", False)
        ),
        on_submit=submit_screening_answer
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
                    st.session_state.screening_ephemeral_status = message
                    st.session_state.screening_ephemeral_after_index = latest_user_message_index

                question_text = data["question_text"]

                st.session_state.screening_messages.append({
                    "role": "assistant",
                    "content": question_text
                })

                st.session_state.screening_session["question_text"] = question_text
                st.session_state.screening_session["question_id"] = data["question_id"]

            elif action == "ask_again":
                ask_again_message = data["message"]

                st.session_state.screening_messages.append({
                    "role": "assistant",
                    "content": ask_again_message
                })

            elif action == "complete":
                completion_message = data.get(
                    "message",
                    "Screening completed. Your responses have been recorded."
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

    if st.button("Reset and start over"):
        reset_screening()