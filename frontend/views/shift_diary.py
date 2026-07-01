from html import escape

import streamlit as st

from shared import api_request


def inject_shift_diary_styles():
    st.markdown(
        """
        <style>

            .shift-diary-chatbot-placeholder {
                height: 180px;
                overflow-y: auto;
                border: 1px solid rgba(148, 163, 184, 0.35);
                border-radius: 0.6rem;
                padding: 0.9rem 1rem;
                margin-bottom: 1.2rem;
                background: rgba(148, 163, 184, 0.06);
            }

            .shift-diary-chatbot-placeholder p {
                margin: 0;
                opacity: 0.7;
            }

            .shift-diary-entry {
                border: 1px solid rgba(148, 163, 184, 0.35);
                border-radius: 0.6rem;
                padding: 0.85rem 1rem;
                margin-bottom: 0.75rem;
                background: rgba(148, 163, 184, 0.06);
            }

            .shift-diary-entry-title {
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .shift-diary-entry-meta {
                font-size: 0.82rem;
                opacity: 0.72;
                margin-bottom: 0.55rem;
            }

            .shift-diary-entry-text {
                line-height: 1.45;
                white-space: pre-wrap;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_datetime(value):
    if not value:
        return "Unknown time"

    return value.replace("T", " ").split(".")[0]


def load_daily_shift_state(token):
    if not token:
        return {
            "state": "unavailable",
            "shift": None,
            "error": "Not signed in.",
        }

    response = api_request(
        "GET",
        "/daily-shifts/current",
        token=token,
    )

    if response is None:
        return {
            "state": "unavailable",
            "shift": None,
            "error": "Daily shift status is unavailable.",
        }

    if response.status_code != 200:
        return {
            "state": "unavailable",
            "shift": None,
            "error": f"Daily shift status unavailable. HTTP {response.status_code}",
        }

    return response.json()


def load_shift_diary_entries(token):
    response = api_request(
        "GET",
        "/daily-shifts/current/diary-entries",
        token=token,
    )

    if response is None:
        return None, "Shift diary entries are unavailable."

    if response.status_code != 200:
        return None, f"Shift diary entries unavailable. HTTP {response.status_code}"

    return response.json(), None


def render_shift_state_guard(shift_state):
    state = shift_state.get("state")

    if state == "active":
        return True

    if state in ("no_shift_today", "ended"):
        st.info("No active shift. Start a shift from the dashboard before using the shift diary.")
        return False

    st.error(shift_state.get("error", "Unable to load daily shift status."))
    return False


def render_info_message():
    st.info(
        """
        Document any food safety incidents such as equipment failures
        (like a broken fridge), or food deliveries that are rejected and
        any corrective actions taken.

        You can use the chatbot below to enquire whether an incident is
        a food safety incident, suggest corrective measures and
        corresponding entries into the diary.
        """
    )


def render_chatbot_placeholder():
    st.markdown(
        """
        <div class="shift-diary-chatbot-placeholder">
            <p>Chatbot functionality will be implemented here in a future phase.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_diary_entry(entry):
    title = escape(entry.get("title") or "Diary entry")
    entry_text = escape(entry.get("entry_text") or "")
    created_at = escape(format_datetime(entry.get("created_at")))
    created_by = escape(entry.get("created_by_name") or "Unknown user")

    st.markdown(
        f"""
        <div class="shift-diary-entry">
            <div class="shift-diary-entry-title">{title}</div>
            <div class="shift-diary-entry-meta">
                Created: {created_at} | Created by: {created_by}
            </div>
            <div class="shift-diary-entry-text">{entry_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show():
    inject_shift_diary_styles()

    st.title("Shift Diary")

    token = st.session_state.get("token")

    if not token:
        st.error("You must be logged in to view the shift diary.")
        return

    shift_state = load_daily_shift_state(token)

    if not render_shift_state_guard(shift_state):
        return

    render_info_message()
    render_chatbot_placeholder()

    st.subheader("Diary Entries")

    entries, error = load_shift_diary_entries(token)

    if error:
        st.error(error)
        return

    if not entries:
        st.info("No diary entries have been recorded for this shift yet.")
        return

    for entry in entries:
        render_diary_entry(entry)