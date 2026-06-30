from html import escape

import streamlit as st

from shared import api_request


def inject_notification_styles():
    st.markdown(
        """
        <style>
            .notifications-header {
                border: 1px solid #d8e1ef;
                border-radius: 12px;
                background: #f8fafc;
                padding: 1rem 1.25rem;
                margin-bottom: 1rem;
            }

            .notifications-title {
                color: #0f172a;
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .notifications-subtitle {
                color: #475569;
                font-size: 0.92rem;
            }

            .notification-card {
                border: 1px solid #d8e1ef;
                border-radius: 12px;
                background: #ffffff;
                padding: 1rem 1.25rem;
                margin-bottom: 0.85rem;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
            }

            .notification-card.unread {
                border-color: #f59e0b;
                background: #fff7ed;
            }

            .notification-title {
                color: #0f172a;
                font-size: 1.05rem;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .notification-message {
                color: #334155;
                font-size: 0.94rem;
                margin-bottom: 0.45rem;
                line-height: 1.4;
            }

            .notification-meta {
                color: #64748b;
                font-size: 0.82rem;
            }

            .notification-status {
                display: inline-block;
                border-radius: 999px;
                padding: 0.18rem 0.55rem;
                font-size: 0.75rem;
                font-weight: 700;
                margin-bottom: 0.35rem;
            }

            .notification-status.unread {
                background: #fed7aa;
                color: #9a3412;
            }

            .notification-status.read {
                background: #e2e8f0;
                color: #475569;
            }

            div[data-testid="stButton"] > button {
                border: 1px solid #c7d2fe !important;
                border-radius: 10px !important;
                background: #eef4ff !important;
                color: #1e3a8a !important;
                font-weight: 700 !important;
                min-height: 40px !important;
            }

            div[data-testid="stButton"] > button:hover {
                border-color: #93c5fd !important;
                background: #e0ecff !important;
                color: #1d4ed8 !important;
            }

            @media (prefers-color-scheme: dark) {
                .notifications-header,
                .notification-card {
                    background: #111827;
                    border-color: #334155;
                }

                .notification-card.unread {
                    background: #1f2937;
                    border-color: #f59e0b;
                }

                .notifications-title,
                .notification-title {
                    color: #f8fafc;
                }

                .notifications-subtitle,
                .notification-message {
                    color: #cbd5e1;
                }

                .notification-meta {
                    color: #f59e0b;
                }
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


def mark_all_notifications_read(token):
    response = api_request(
        "PATCH",
        "/notifications/read-all",
        token=token,
    )

    if response is None:
        st.error("Unable to connect to the backend.")
        return False

    if response.status_code != 200:
        st.error(f"Unable to mark notifications as read. HTTP {response.status_code}")
        return False

    data = response.json()
    st.success(f"{data.get('updated_count', 0)} notification(s) marked as read.")
    return True


def render_header(unread_count):
    st.markdown(
        f"""
        <div class="notifications-header">
            <div class="notifications-title">Notifications</div>
            <div class="notifications-subtitle">
                You have {unread_count} unread notification(s).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_notification_card(token, notification):
    notification_id = notification["id"]
    status = notification.get("status", "unread")
    css_status = "unread" if status == "unread" else "read"
    title = escape(notification.get("title") or "Notification")
    message = escape(notification.get("message") or "")
    notification_type = escape(notification.get("notification_type") or "system")
    created_at = escape(format_datetime(notification.get("created_at")))
    action_route = notification.get("action_route")

    st.markdown(
        f"""
        <div class="notification-card {css_status}">
            <div class="notification-status {css_status}">{escape(status.upper())}</div>
            <div class="notification-title">{title}</div>
            <div class="notification-message">{message}</div>
            <div class="notification-meta">
                Type: {notification_type} &nbsp;|&nbsp; Created: {created_at}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    button_cols = st.columns([1, 1, 3])

    with button_cols[0]:
        if status == "unread":
            if st.button(
                "Mark as read",
                key=f"mark_notification_read_{notification_id}",
                use_container_width=True,
            ):
                if mark_notification_read(token, notification_id):
                    st.rerun()
        else:
            st.button(
                "Read",
                key=f"notification_already_read_{notification_id}",
                use_container_width=True,
                disabled=True,
            )

    with button_cols[1]:
        if action_route:
            if st.button(
                "Open action",
                key=f"open_notification_action_{notification_id}",
                use_container_width=True,
            ):
                st.session_state.page = action_route
                st.rerun()
        else:
            st.button(
                "No action",
                key=f"notification_no_action_{notification_id}",
                use_container_width=True,
                disabled=True,
            )


def show():
    inject_notification_styles()

    token = st.session_state.get("token")

    if not token:
        st.error("You must be logged in to view notifications.")
        return

    notifications = load_notifications(token)

    if notifications is None:
        return

    unread_count = sum(
        1 for notification in notifications
        if notification.get("status") == "unread"
    )

    render_header(unread_count)

    top_cols = st.columns([1, 1, 3])

    with top_cols[0]:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    with top_cols[1]:
        if st.button("Mark all as read", use_container_width=True):
            if mark_all_notifications_read(token):
                st.rerun()

    if not notifications:
        st.info("No notifications yet.")
        return

    for notification in notifications:
        render_notification_card(token, notification)