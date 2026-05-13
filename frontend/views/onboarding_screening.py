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
        if resp and resp.status_code == 200:
            return resp.json()
        elif resp and resp.status_code == 404:
            return None
        else:
            st.error("Failed to load session. Please try again.")
            return None

    def start_session():
        resp = api_request("POST", "/onboarding/screening/start", token=token)
        if resp and resp.status_code == 200:
            return resp.json()
        else:
            st.error("Could not start screening. Check backend logs.")
            return None

    if "screening_session" not in st.session_state:
        st.session_state.screening_session = None
    if "screening_messages" not in st.session_state:
        st.session_state.screening_messages = []

    current = load_current_session()
    if current:
        st.session_state.screening_session = current
        if not st.session_state.screening_messages:
            st.session_state.screening_messages.append({
                "role": "assistant",
                "content": current["question_text"]
            })
    else:
        if st.button("Start onboarding"):
            new_session = start_session()
            if new_session:
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

    user_input = st.chat_input("Type your answer here...")
    if user_input:
        st.chat_message("user").write(user_input)
        st.session_state.screening_messages.append({"role": "user", "content": user_input})

        resp = api_request("POST", "/onboarding/screening/answer", json={"answer": user_input}, token=token)
        if resp and resp.status_code == 200:
            data = resp.json()
            action = data.get("action")
            if action == "next_question":
                question_text = data["question_text"]
                st.chat_message("assistant").write(question_text)
                st.session_state.screening_messages.append({"role": "assistant", "content": question_text})
                st.session_state.screening_session["question_text"] = question_text
                st.session_state.screening_session["question_id"] = data["question_id"]
            elif action == "clarify":
                clarification = data["clarification_question"]
                st.chat_message("assistant").write(clarification)
                st.session_state.screening_messages.append({"role": "assistant", "content": clarification})
            elif action == "retry":
                st.chat_message("assistant").write("Please answer the question directly.")
                st.session_state.screening_messages.append({"role": "assistant", "content": "Please answer the question directly."})
            elif action == "complete":
                st.chat_message("assistant").write("Screening completed! You can now proceed to safety point approval.")
                st.session_state.screening_session = None
                st.session_state.screening_messages = []
                st.rerun()
        else:
            st.error("Failed to process answer. Check backend logs.")

    if st.button("Reset and start over"):
        st.session_state.screening_session = None
        st.session_state.screening_messages = []
        st.rerun()
