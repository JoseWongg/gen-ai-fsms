from html import escape

import streamlit as st

from shared import api_request


ACTION_ROUTE_LABELS = {
    "dashboard": "Dashboard",
    "notifications": "Notifications",
    "shift_checklist": "Checklist",
    "shift_diary": "Diary",
    "shift_archive": "Archive",
}

CHILLING_TEMPERATURE_INCIDENT_ENTITY_TYPE = "chilling_temperature_incident"

def inject_notification_styles():
    st.markdown(
        """
        <style>
            .notifications-header {
                margin-bottom: 1.25rem;
            }

            .notifications-header h2 {
                margin-bottom: 0.2rem;
            }

            .notifications-header p {
                margin-top: 0;
                opacity: 0.75;
            }

            div[data-testid="stButton"] > button {
                text-align: left !important;
                justify-content: flex-start !important;
            }

            div[data-testid="stButton"] > button div[data-testid="stMarkdownContainer"] {
                width: 100% !important;
                text-align: left !important;
            }

            div[data-testid="stButton"] > button div[data-testid="stMarkdownContainer"] p {
                width: 100% !important;
                text-align: left !important;
            }

            .notification-message-body {
                max-height: 220px;
                overflow-y: auto;
                padding: 0.85rem;
                border: 1px solid rgba(128, 128, 128, 0.25);
                border-radius: 0.5rem;
                margin-top: 0.4rem;
                margin-bottom: 0.7rem;
                line-height: 1.45;
                white-space: pre-wrap;
            }

            .notification-meta {
                font-size: 0.82rem;
                opacity: 0.72;
                margin-bottom: 0.5rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_datetime(value):
    if not value:
        return "Unknown time"

    return value.replace("T", " ").split(".")[0]


def load_notifications(token):
    response = api_request(
        "GET",
        "/notifications",
        token=token,
    )

    if response is None:
        st.error("Unable to connect to the backend.")
        return None

    if response.status_code != 200:
        st.error(f"Unable to load notifications. HTTP {response.status_code}")
        return None

    return response.json()


def mark_notification_read(token, notification_id):
    response = api_request(
        "PATCH",
        f"/notifications/{notification_id}/read",
        token=token,
    )

    if response is None:
        st.error("Unable to connect to the backend.")
        return False

    if response.status_code != 200:
        st.error(f"Unable to mark notification as read. HTTP {response.status_code}")
        return False

    return True


def get_response_error_message(response, fallback_message):
    if response is None:
        return "Unable to connect to the backend."

    try:
        data = response.json()
    except ValueError:
        return f"{fallback_message} HTTP {response.status_code}"

    detail = data.get("detail")
    if detail:
        return str(detail)

    return f"{fallback_message} HTTP {response.status_code}"


def start_corrective_action_session(token, incident_id):
    response = api_request(
        "POST",
        f"/chilling-temperature-incidents/{incident_id}/corrective-action/session",
        token=token,
    )

    if response is None or response.status_code != 200:
        return None, get_response_error_message(
            response,
            "Unable to start corrective-action session.",
        )

    return response.json(), None


def send_corrective_action_message(token, incident_id, message):
    response = api_request(
        "POST",
        f"/chilling-temperature-incidents/{incident_id}/corrective-action/message",
        json={"message": message},
        token=token,
    )

    if response is None or response.status_code != 200:
        return None, get_response_error_message(
            response,
            "Unable to send corrective-action message.",
        )

    return response.json(), None


def approve_corrective_action_summary(token, incident_id):
    response = api_request(
        "POST",
        f"/chilling-temperature-incidents/{incident_id}/corrective-action/approve",
        token=token,
    )

    if response is None or response.status_code != 200:
        return None, get_response_error_message(
            response,
            "Unable to approve corrective-action summary.",
        )

    return response.json(), None


def render_header(unread_count):
    st.markdown(
        f"""
        <div class="notifications-header">
            <h2>Notifications</h2>
            <p>{unread_count} unread notification(s).</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def open_notification_action(action_route):
    route_label = ACTION_ROUTE_LABELS.get(action_route)

    st.session_state.pending_navigation_route = action_route

    if route_label:
        st.session_state.pending_navigation_label = route_label

    st.rerun()


def is_chilling_temperature_incident_notification(notification):
    return (
        notification.get("related_entity_type")
        == CHILLING_TEMPERATURE_INCIDENT_ENTITY_TYPE
        and notification.get("related_entity_id") is not None
    )


def open_corrective_action_workflow(notification):
    incident_id = notification["related_entity_id"]

    if (
        st.session_state.get("selected_corrective_action_incident_id")
        != incident_id
    ):
        st.session_state.pop("corrective_action_workflow_response", None)
        st.session_state.pop("corrective_action_workflow_error", None)

    st.session_state.selected_corrective_action_incident_id = incident_id
    st.session_state.corrective_action_dialog_open = True
    st.session_state.corrective_action_source_notification_id = notification[
        "id"
    ]

    st.rerun()


def clear_corrective_action_dialog_state():
    st.session_state.pop("selected_corrective_action_incident_id", None)
    st.session_state.pop("corrective_action_dialog_open", None)
    st.session_state.pop("corrective_action_source_notification_id", None)
    st.session_state.pop("corrective_action_workflow_response", None)
    st.session_state.pop("corrective_action_workflow_error", None)



def get_corrective_action_equipment_label(workflow_response):
    if not workflow_response:
        return "chilling equipment"

    equipment_type = workflow_response.get("equipment_type")

    if equipment_type == "fridge":
        return "fridge"

    if equipment_type == "freezer":
        return "freezer"

    return "chilling equipment"


def render_corrective_action_workflow_response(workflow_response):
    if not workflow_response:
        return

    stage = workflow_response.get("stage")
    message = workflow_response.get("message")
    final_summary = workflow_response.get("final_summary")
    issues = workflow_response.get("issues") or []
    is_completed = workflow_response.get("is_completed", False)

    if is_completed:
        st.success(message or "Corrective action recorded and incident resolved.")
        return

    if stage == "awaiting_approval" and final_summary:
        st.markdown("**Final corrective-action summary**")
        st.info(final_summary)
        if message:
            st.caption(message)
        return

    if message:
        st.info(message)

    if issues:
        with st.expander("Validation details", expanded=False):
            for issue in issues:
                issue_message = issue.get("message") or "Validation issue."
                issue_kind = issue.get("kind") or "issue"
                st.write(f"**{issue_kind}:** {issue_message}")


@st.dialog("Corrective action", on_dismiss=clear_corrective_action_dialog_state)
def render_corrective_action_dialog(token, incident_id):
    workflow_response = st.session_state.get("corrective_action_workflow_response")
    workflow_error = st.session_state.pop("corrective_action_workflow_error", None)

    if workflow_response is None:
        workflow_response, workflow_error = start_corrective_action_session(
            token=token,
            incident_id=incident_id,
        )
        if workflow_response is not None:
            st.session_state.corrective_action_workflow_response = workflow_response

    if workflow_error:
        st.error(workflow_error)
        if st.button("Close", use_container_width=True):
            clear_corrective_action_dialog_state()
            st.rerun()
        return

    if not (workflow_response and workflow_response.get("is_completed")):
        equipment_label = get_corrective_action_equipment_label(workflow_response)
        st.markdown(
            f"Describe the corrective action taken for this {equipment_label} "
            "temperature incident."
        )

    render_corrective_action_workflow_response(workflow_response)

    if workflow_response and workflow_response.get("is_completed"):
        if st.button("Close", use_container_width=True):
            clear_corrective_action_dialog_state()
            st.rerun()
        return

    if (
        workflow_response
        and workflow_response.get("stage") == "awaiting_approval"
        and workflow_response.get("final_summary")
    ):
        approve_column, close_column = st.columns(2)

        with approve_column:
            if st.button("Approve summary", use_container_width=True):
                response_data, error = approve_corrective_action_summary(
                    token=token,
                    incident_id=incident_id,
                )

                if error:
                    st.session_state.corrective_action_workflow_error = error
                else:
                    st.session_state.corrective_action_workflow_response = (
                        response_data
                    )

                st.rerun()

        with close_column:
            if st.button("Close", use_container_width=True):
                clear_corrective_action_dialog_state()
                st.rerun()

        correction = st.text_area(
            "Correction or extra detail",
            key=f"corrective_action_correction_{incident_id}",
            placeholder="Enter a correction if the summary is not accurate.",
        )

        if st.button("Send correction", use_container_width=True):
            if not correction.strip():
                st.warning("Enter a correction before sending.")
            else:
                response_data, error = send_corrective_action_message(
                    token=token,
                    incident_id=incident_id,
                    message=correction,
                )

                if error:
                    st.session_state.corrective_action_workflow_error = error
                else:
                    st.session_state.corrective_action_workflow_response = (
                        response_data
                    )

                st.rerun()

        return

    user_message = st.text_area(
        "Corrective action taken",
        key=f"corrective_action_message_{incident_id}",
        placeholder=(
            "Example: I probed the food, confirmed it had been warm for less "
            "than four hours, moved it to a compliant fridge, corrected the "
            "fridge issue, and rechecked the fridge temperature."
        ),
    )

    send_column, close_column = st.columns(2)

    with send_column:
        if st.button("Send", use_container_width=True):
            if not user_message.strip():
                st.warning("Enter the corrective action before sending.")
            else:
                response_data, error = send_corrective_action_message(
                    token=token,
                    incident_id=incident_id,
                    message=user_message,
                )

                if error:
                    st.session_state.corrective_action_workflow_error = error
                else:
                    st.session_state.corrective_action_workflow_response = (
                        response_data
                    )

                st.rerun()

    with close_column:
        if st.button("Close", use_container_width=True):
            clear_corrective_action_dialog_state()
            st.rerun()


def toggle_notification(token, notification):
    notification_id = notification["id"]
    status = notification.get("status", "unread")
    currently_expanded_id = st.session_state.get("expanded_notification_id")

    if currently_expanded_id == notification_id:
        st.session_state.expanded_notification_id = None
        st.rerun()

    st.session_state.expanded_notification_id = notification_id

    if status == "unread":
        if not mark_notification_read(token, notification_id):
            st.session_state.expanded_notification_id = None
            return

    st.rerun()


def render_notification_item(token, notification):
    notification_id = notification["id"]
    status = notification.get("status", "unread")
    is_unread = status == "unread"
    is_expanded = st.session_state.get("expanded_notification_id") == notification_id

    title = notification.get("title") or "Notification"
    status_marker = "🟠" if is_unread else "○"
    title_label = f"{status_marker} {title}"

    if st.button(
        title_label,
        key=f"toggle_notification_{notification_id}",
    ):
        toggle_notification(token, notification)

    if not is_expanded:
        return

    message = escape(notification.get("message") or "")
    created_at = escape(format_datetime(notification.get("created_at")))
    action_route = notification.get("action_route")

    with st.container(border=True):
        st.markdown(
            f"""
            <div class="notification-meta">
                Created: {created_at}
            </div>
            <div class="notification-message-body">
                {message}
            </div>
            """,
            unsafe_allow_html=True,
        )

        if action_route:
            if st.button(
                "Open action",
                key=f"open_notification_action_{notification_id}",
                use_container_width=True,
            ):
                if is_chilling_temperature_incident_notification(notification):
                    open_corrective_action_workflow(notification)
                else:
                    open_notification_action(action_route)


def show():
    inject_notification_styles()

    token = st.session_state.get("token")

    if not token:
        st.error("You must be logged in to view notifications.")
        return

    if "expanded_notification_id" not in st.session_state:
        st.session_state.expanded_notification_id = None

    notifications = load_notifications(token)

    if notifications is None:
        return

    unread_count = sum(
        1
        for notification in notifications
        if notification.get("status") == "unread"
    )

    render_header(unread_count)

    if not notifications:
        st.info("No notifications yet.")
        return

    for notification in notifications:
        render_notification_item(token, notification)


    selected_incident_id = st.session_state.get(
        "selected_corrective_action_incident_id"
    )

    if (
        st.session_state.get("corrective_action_dialog_open")
        and selected_incident_id is not None
    ):
        render_corrective_action_dialog(
            token=token,
            incident_id=selected_incident_id,
        )
