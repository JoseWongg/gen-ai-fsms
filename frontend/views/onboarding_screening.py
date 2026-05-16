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
            # Connection error – treat as no session (backend may be starting)
            return None
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 404:
            return None

        st.error(f"Failed to load session (HTTP {resp.status_code}). Please try again.")
        return None

    def start_session():
        resp = api_request("POST", "/onboarding/screening/start", token=token)
        if resp and resp.status_code == 200:
            return resp.json()

        st.error("Could not start screening. Check backend logs.")
        return None

    if "screening_session" not in st.session_state:
        st.session_state.screening_session = None
    if "screening_messages" not in st.session_state:
        st.session_state.screening_messages = []
    if "screening_status_messages" not in st.session_state:
        st.session_state.screening_status_messages = []
    if "screening_complete" not in st.session_state:
        st.session_state.screening_complete = False
    if "screening_processing" not in st.session_state:
        st.session_state.screening_processing = False
    if "pending_screening_answer" not in st.session_state:
        st.session_state.pending_screening_answer = None

    current = load_current_session()
    if current:
        st.session_state.screening_session = current
        if not st.session_state.screening_messages:
            st.session_state.screening_messages.append({
                "role": "assistant",
                "content": current["question_text"]
            })
    else:
        if not st.session_state.get("screening_complete"):
            if st.button("Start onboarding"):
                new_session = start_session()
                if new_session:
                    st.session_state.screening_complete = False
                    st.session_state.screening_processing = False
                    st.session_state.pending_screening_answer = None
                    st.session_state.screening_session = new_session
                    st.session_state.screening_messages.append({
                        "role": "assistant",
                        "content": new_session["question_text"]
                    })
                    st.rerun()

            st.info("Click 'Start onboarding' to begin the screening process.")
            return

    # Display conversation
    for msg in st.session_state.screening_messages:
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        else:
            st.chat_message("assistant").write(msg["content"])

    # Display processing or latest status message
    if st.session_state.get("screening_processing", False):
        st.info("Processing your response...")
    elif st.session_state.get("screening_status_messages"):
        st.info(st.session_state.screening_status_messages[-1])

    user_input = st.chat_input(
        "Type your answer here...",
        disabled=(
            st.session_state.get("screening_complete", False)
            or st.session_state.get("screening_processing", False)
        )
    )

    if user_input and not st.session_state.get("screening_processing", False):
        st.session_state.screening_messages.append({
            "role": "user",
            "content": user_input
        })
        st.session_state.pending_screening_answer = user_input
        st.session_state.screening_processing = True
        st.rerun()

    if (
        st.session_state.get("screening_processing", False)
        and st.session_state.get("pending_screening_answer")
    ):
        pending_answer = st.session_state.pending_screening_answer

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

            if message and action not in ("ask_again",):
                st.session_state.screening_status_messages.append(message)

            if action == "next_question":
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
                st.session_state.screening_session = None

            else:
                st.session_state.screening_status_messages.append(
                    "Unexpected response from server."
                )

        else:
            st.session_state.screening_status_messages.append(
                "Failed to process answer. Check backend logs."
            )

        st.rerun()

    if st.button("Reset and start over"):
        resp = api_request("POST", "/onboarding/screening/reset", token=token)
        if resp and resp.status_code == 200:
            st.session_state.screening_session = None
            st.session_state.screening_messages = []
            st.session_state.screening_status_messages = []
            st.session_state.screening_complete = False
            st.session_state.screening_processing = False
            st.session_state.pending_screening_answer = None
            st.rerun()
        else:
            st.error("Failed to reset screening. Check backend logs.")