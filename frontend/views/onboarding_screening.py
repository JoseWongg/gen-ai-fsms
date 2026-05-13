import streamlit as st
from shared import api_request

def show():
    st.title("Onboarding – Screening Chatbot")

    # Admin check (the page should only be visible to admins, but we also enforce on API)
    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("You must be an admin to access onboarding.")
        return

    # Helper to load current session
    def load_current_session():
        resp = api_request("GET", "/onboarding/screening/current")
        if resp and resp.status_code == 200:
            return resp.json()
        elif resp and resp.status_code == 404:
            return None
        else:
            st.error("Failed to load session. Please try again.")
            return None

    # Helper to start a new session
    def start_session():
        resp = api_request("POST", "/onboarding/screening/start")
        if resp and resp.status_code == 200:
            return resp.json()
        else:
            st.error("Could not start screening. Check backend logs.")
            return None

    session_state = st.session_state
    if "screening_session" not in session_state:
        session_state.screening_session = None
    if "screening_messages" not in session_state:
        session_state.screening_messages = []

    # Try to load existing session
    current = load_current_session()
    if current:
        session_state.screening_session = current
        # If messages are empty, add system question
        if not session_state.screening_messages:
            session_state.screening_messages.append({
                "role": "assistant",
                "content": current["question_text"]
            })
    else:
        # No active session – show start button
        if st.button("Start onboarding"):
            new_session = start_session()
            if new_session:
                session_state.screening_session = new_session
                session_state.screening_messages.append({
                    "role": "assistant",
                    "content": new_session["question_text"]
                })
                st.rerun()
        st.info("Click 'Start onboarding' to begin the screening process.")
        return

    # We have an active session – display chat interface
    session = session_state.screening_session

    # Display conversation history
    for msg in session_state.screening_messages:
        if msg["role"] == "user":
            st.chat_message("user").write(msg["content"])
        else:
            st.chat_message("assistant").write(msg["content"])

    # Input for answer
    user_input = st.chat_input("Type your answer here...")
    if user_input:
        # Add user message to UI
        st.chat_message("user").write(user_input)
        session_state.screening_messages.append({"role": "user", "content": user_input})

        # Send answer to backend
        resp = api_request("POST", "/onboarding/screening/answer", json={"answer": user_input})
        if resp and resp.status_code == 200:
            data = resp.json()
            action = data.get("action")
            if action == "next_question":
                # New question
                question_text = data["question_text"]
                st.chat_message("assistant").write(question_text)
                session_state.screening_messages.append({"role": "assistant", "content": question_text})
                # Update local session ID (unchanged) and question
                session_state.screening_session["question_text"] = question_text
                session_state.screening_session["question_id"] = data["question_id"]
            elif action == "clarify":
                # Clarification question
                clarification = data["clarification_question"]
                st.chat_message("assistant").write(clarification)
                session_state.screening_messages.append({"role": "assistant", "content": clarification})
            elif action == "retry":
                # Unrelated answer – ask to re‑answer
                st.chat_message("assistant").write("Please answer the question directly.")
                session_state.screening_messages.append({"role": "assistant", "content": "Please answer the question directly."})
            elif action == "complete":
                st.chat_message("assistant").write("Screening completed! You can now proceed to safety point approval.")
                session_state.screening_session = None
                session_state.screening_messages = []
                st.rerun()
        else:
            st.error("Failed to process answer. Check backend logs.")

    # Show resume button
    if st.button("Reset and start over"):
        session_state.screening_session = None
        session_state.screening_messages = []
        st.rerun()
