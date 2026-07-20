from html import escape

import streamlit as st

from shared import api_request


RECENT_ACTIVITY_ITEMS = [
    ("Fridge 2 temperature recorded: 4.2°C", "10 mins ago", "normal"),
    ("Freezer 1 above threshold: 6.1°C", "25 mins ago", "alert"),
    ("Morning cleaning checklist completed", "1 hour ago", "normal"),
    ("Sarah completed Food Hygiene training", "2 hours ago", "normal"),
    ("Equipment service log updated - Oven 1", "3 hours ago", "warning"),
    ("Equipment maintenance due in 3 days: Dishwasher", "4 hours ago", "warning"),
    ("Food delivery inspection completed", "5 hours ago", "normal"),
    ("All morning temperature checks completed", "6 hours ago", "normal"),
]


def inject_dashboard_styles():
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1180px !important;
                padding-top: 1.5rem !important;
                padding-left: 1.5rem !important;
                padding-right: 1.5rem !important;
            }

            .top-spacer {
                height: 2rem;
            }

            .quick-grid {
                display: grid;
                grid-template-columns: repeat(5, minmax(130px, 1fr));
                gap: 1rem;
                margin-bottom: 1.8rem;
            }

            .quick-card {
                border: 1px solid #d8e1ef;
                border-radius: 12px;
                min-height: 128px;
                padding: 1rem;
                text-align: center;
                background: #ffffff;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
            }

            .quick-card-icon {
                width: 46px;
                height: 46px;
                border-radius: 10px;
                background: #edf2ff;
                color: #2563eb;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.72rem;
                font-weight: 700;
                margin-bottom: 0.85rem;
            }

            .quick-card-title {
                color: #0f172a;
                font-size: 0.95rem;
                line-height: 1.25;
                font-weight: 500;
            }

            .section-title {
                color: #0f172a;
                font-size: 1.45rem;
                font-weight: 700;
                margin-top: 0.5rem;
                margin-bottom: 1rem;
            }

            .status-grid {
                display: grid;
                grid-template-columns: repeat(4, minmax(210px, 1fr));
                gap: 1rem;
                margin-bottom: 1.8rem;
            }

            .status-card,
            .workflow-card {
                border: 1px solid #f6c96b;
                border-radius: 12px;
                min-height: 230px;
                padding: 1.25rem 1rem;
                text-align: center;
                background: #fffdf8;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
            }

            .status-card.green {
                border-color: #9bd7b5;
                background: #f2fbf6;
            }

            .status-card.red {
                border-color: #ffabab;
                background: #fff6f7;
            }

            .status-icon {
                width: 46px;
                height: 46px;
                border-radius: 10px;
                background: #ffe7b3;
                color: #f59e0b;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.72rem;
                font-weight: 700;
                margin-bottom: 0.8rem;
            }

            .status-icon.green {
                background: #c7efd8;
                color: #079455;
            }

            .status-icon.red {
                background: #ffd0d6;
                color: #f04438;
            }

            .status-title,
            .workflow-title {
                color: #475569;
                font-size: 1rem;
                font-weight: 600;
                margin-bottom: 0.45rem;
            }

            .status-value {
                color: #f59e0b;
                font-size: 1.9rem;
                font-weight: 700;
                margin-bottom: 0.3rem;
            }

            .status-value.green {
                color: #079455;
            }

            .status-value.red {
                color: #f04438;
            }

            .status-caption,
            .workflow-caption {
                color: #475569;
                font-size: 0.88rem;
                line-height: 1.35;
            }

            .donut {
                --progress: 0deg;
                width: 112px;
                height: 112px;
                border-radius: 50%;
                background:
                    conic-gradient(#38bdf8 var(--progress), #e5e7eb 0deg);
                display: flex;
                align-items: center;
                justify-content: center;
                margin-top: 0.3rem;
                margin-bottom: 0.75rem;
            }

            .donut-inner {
                width: 72px;
                height: 72px;
                border-radius: 50%;
                background: #fffdf8;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #0f172a;
                font-size: 1.15rem;
                font-weight: 700;
            }

            .workflow-value {
                color: #f59e0b;
                font-size: 1.45rem;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .button-spacer {
                height: 0.35rem;
            }

            div[data-testid="stButton"] > button {
                border: 1px solid #c7d2fe !important;
                border-radius: 10px !important;
                background: #eef4ff !important;
                color: #1e3a8a !important;
                font-weight: 700 !important;
                min-height: 44px !important;
                box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06) !important;
            }

            div[data-testid="stButton"] > button:hover {
                border-color: #93c5fd !important;
                background: #e0ecff !important;
                color: #1d4ed8 !important;
            }

            div[data-testid="stButton"] > button:disabled {
                border: 1px solid #c7d2fe !important;
                background: #eef4ff !important;
                color: #1e3a8a !important;
                opacity: 1 !important;
            }

            .activity-card {
                border: 1px solid #334155;
                border-radius: 12px;
                background: #111827;
                padding: 1rem 1.25rem;
                box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
                margin-top: 1rem;
                margin-bottom: 1rem;
            }

            .activity-heading {
                color: #f59e0b !important;
                font-size: 1.2rem;
                font-weight: 700;
             margin-bottom: 0.75rem;
            }

            .activity-scroll {
                max-height: 320px;
                overflow-y: auto;
                padding-right: 0.5rem;
            }

            .activity-item {
                display: grid;
                grid-template-columns: 42px 1fr;
                column-gap: 0.9rem;
                align-items: center;
                padding: 0.6rem 0;
            }

            .activity-dot {
                width: 36px;
                height: 36px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.68rem;
                font-weight: 700;
            }

            .activity-dot.normal {
                background: #e8f8ee;
                color: #079455;
            }

            .activity-dot.warning {
                background: #fff1d6;
                color: #f59e0b;
            }

            .activity-dot.alert {
                background: #ffe5e8;
                color: #f04438;
            }

            .activity-title {
                color: #0f172a !important;
                font-size: 0.98rem;
                font-weight: 500;
                margin-bottom: 0.05rem;
            }

            .activity-time {
                color: #475569 !important;
                font-size: 0.86rem;
            }

            @media (max-width: 1200px) {
                .quick-grid {
                    grid-template-columns: repeat(3, minmax(150px, 1fr));
                }

                .status-grid {
                    grid-template-columns: repeat(2, minmax(230px, 1fr));
                }
            }

            @media (max-width: 760px) {
                .block-container {
                    padding-left: 1rem !important;
                    padding-right: 1rem !important;
                }

                .quick-grid {
                    grid-template-columns: 1fr;
                }

                .status-grid {
                    grid-template-columns: 1fr;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_food_safety_profile_progress(token):
    if not token:
        return {
            "title": "Food Safety Profile",
            "status": "Not signed in",
            "progress_percentage": 0,
            "main_value": "0%",
            "caption": "Workflow progress unavailable",
        }

    response = api_request(
        "GET",
        "/onboarding/screening/condition-values",
        token=token,
    )

    if response is None or response.status_code == 404:
        return {
            "title": "Food Safety Profile",
            "status": "Not started",
            "progress_percentage": 0,
            "main_value": "0%",
            "caption": "Profile not completed",
        }

    if response.status_code != 200:
        return {
            "title": "Food Safety Profile",
            "status": "Unavailable",
            "progress_percentage": 0,
            "main_value": "0%",
            "caption": f"HTTP {response.status_code}",
        }

    data = response.json()
    active_count = data.get("active_condition_count", 0) or 0
    completed_count = data.get("completed_active_condition_count", 0) or 0

    if active_count <= 0:
        progress_percentage = 100 if data.get("is_complete") else 0
    else:
        progress_percentage = round((completed_count / active_count) * 100)

    status = "Completed" if data.get("is_complete") else "In progress"

    return {
        "title": "Food Safety Profile",
        "status": status,
        "progress_percentage": progress_percentage,
        "main_value": f"{completed_count}/{active_count}",
        "caption": "Conditions confirmed",
    }


def load_fsms_builder_progress(token):
    if not token:
        return {
            "title": "FSMS Builder",
            "status": "Not signed in",
            "progress_percentage": 0,
            "main_value": "0%",
            "caption": "Workflow progress unavailable",
        }

    response = api_request(
        "GET",
        "/onboarding/safety-points/current",
        token=token,
    )

    if response is None or response.status_code == 404:
        readiness_response = api_request(
            "GET",
            "/onboarding/safety-points/readiness",
            token=token,
        )

        if readiness_response and readiness_response.status_code == 200:
            readiness = readiness_response.json()

            total_count = (
                readiness.get("total_relevant_safety_points")
                or readiness.get("total_count")
                or readiness.get("relevant_safety_point_count")
                or 0
            )

            if readiness.get("is_ready"):
                return {
                    "title": "FSMS Builder",
                    "status": "Ready to start",
                    "progress_percentage": 0,
                    "main_value": f"0/{total_count}" if total_count else "0%",
                    "caption": "Safety point approval not started",
                }

        return {
            "title": "FSMS Builder",
            "status": "Waiting",
            "progress_percentage": 0,
            "main_value": "0%",
            "caption": "Complete Food Safety Profile first",
        }

    if response.status_code != 200:
        return {
            "title": "FSMS Builder",
            "status": "Unavailable",
            "progress_percentage": 0,
            "main_value": "0%",
            "caption": f"HTTP {response.status_code}",
        }

    data = response.json()
    progress = data.get("progress") or {}

    total_count = progress.get("total_count", 0) or 0
    approved_count = progress.get("approved_count", 0) or 0

    if total_count <= 0:
        progress_percentage = 100 if data.get("workflow_status") == "completed" else 0
    else:
        progress_percentage = round((approved_count / total_count) * 100)

    if data.get("workflow_status") == "completed":
        status = "Completed"
        progress_percentage = 100
    else:
        status = "In progress"

    return {
        "title": "FSMS Builder",
        "status": status,
        "progress_percentage": progress_percentage,
        "main_value": f"{approved_count}/{total_count}",
        "caption": "Safety points approved",
    }


def format_dashboard_percentage(value):
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return "0%"

    if numeric_value.is_integer():
        return f"{int(numeric_value)}%"

    return f"{numeric_value:.1f}%"


def load_fsms_document_dashboard_progress(token):
    default_card = {
        "icon_label": "DOC",
        "title": "FSMS Document",
        "value": "0%",
        "caption": "Progress unavailable",
        "colour_class": "",
    }

    if not token:
        return default_card

    response = api_request(
        "GET",
        "/fsms-document/progress",
        token=token,
    )

    if response is None:
        return default_card

    if response.status_code != 200:
        return default_card

    data = response.json()

    completion_percentage = (
        data.get("completion_percentage", 0)
        or 0
    )
    completed_count = (
        data.get(
            "completed_applicable_section_count",
            0,
        )
        or 0
    )
    applicable_count = (
        data.get(
            "applicable_supported_section_count",
            0,
        )
        or 0
    )
    supported_count = (
        data.get("supported_section_count", 0)
        or 0
    )
    planned_count = (
        data.get("planned_section_count", 0)
        or 0
    )
    screening_complete = (
        data.get("screening_complete") is True
    )

    try:
        numeric_percentage = float(
            completion_percentage
        )
    except (TypeError, ValueError):
        numeric_percentage = 0

    if screening_complete:
        caption = (
            f"{completed_count}/{applicable_count} "
            f"current · {supported_count}/"
            f"{planned_count} supported"
        )
    else:
        caption = (
            "Food Safety Profile not completed · "
            f"{supported_count}/{planned_count} "
            "supported"
        )

    return {
        "icon_label": "DOC",
        "title": "FSMS Document",
        "value": format_dashboard_percentage(
            numeric_percentage
        ),
        "caption": caption,
        "colour_class": (
            "green"
            if numeric_percentage >= 100
            else ""
        ),
    }


def load_fridge_temperature_dashboard_progress(token):
    if not token:
        return {
            "icon_label": "FRG",
            "title": "Fridge Temps",
            "value": "0%",
            "caption": "Progress unavailable",
            "colour_class": "",
        }

    response = api_request(
        "GET",
        "/daily-shifts/current/fridge-temperature-progress",
        token=token,
    )

    if response is None:
        return {
            "icon_label": "FRG",
            "title": "Fridge Temps",
            "value": "0%",
            "caption": "Progress unavailable",
            "colour_class": "",
        }

    if response.status_code == 400:
        return {
            "icon_label": "FRG",
            "title": "Fridge Temps",
            "value": "0%",
            "caption": "No active shift",
            "colour_class": "",
        }

    if response.status_code != 200:
        return {
            "icon_label": "FRG",
            "title": "Fridge Temps",
            "value": "0%",
            "caption": f"HTTP {response.status_code}",
            "colour_class": "",
        }

    data = response.json()

    progress_percentage = data.get("progress_percentage", 0)
    completed_count = data.get("completed_temperature_count", 0) or 0
    required_count = data.get("required_temperature_count", 0) or 0

    if required_count == 0:
        caption = "No temperature rows"
    elif completed_count == 1:
        caption = f"{completed_count}/{required_count} temperature"
    else:
        caption = f"{completed_count}/{required_count} temperatures"

    colour_class = "green" if float(progress_percentage) >= 100 else ""

    return {
        "icon_label": "FRG",
        "title": "Fridge Temps",
        "value": format_dashboard_percentage(progress_percentage),
        "caption": caption,
        "colour_class": colour_class,
    }


def load_daily_shift_incident_summary_cards(token):
    default_cards = {
        "unresolved_incidents": {
            "icon_label": "INC",
            "title": "Unresolved Incidents",
            "value": "0",
            "caption": "No active shift",
            "colour_class": "",
        },
        "temp_alerts": {
            "icon_label": "TMP",
            "title": "Temp Alerts",
            "value": "0",
            "caption": "No active shift",
            "colour_class": "",
        },
    }

    if not token:
        return default_cards

    response = api_request(
        "GET",
        "/daily-shifts/current/incident-summary",
        token=token,
    )

    if response is None:
        default_cards["unresolved_incidents"]["caption"] = "Summary unavailable"
        default_cards["temp_alerts"]["caption"] = "Summary unavailable"
        return default_cards

    if response.status_code != 200:
        default_cards["unresolved_incidents"]["caption"] = f"HTTP {response.status_code}"
        default_cards["temp_alerts"]["caption"] = f"HTTP {response.status_code}"
        return default_cards

    data = response.json()

    unresolved_incident_count = data.get("unresolved_incident_count", 0) or 0
    temp_alert_count = data.get("temp_alert_count", 0) or 0

    default_cards["unresolved_incidents"]["value"] = str(unresolved_incident_count)
    default_cards["temp_alerts"]["value"] = str(temp_alert_count)

    if unresolved_incident_count == 1:
        default_cards["unresolved_incidents"]["caption"] = "Open incident"
    else:
        default_cards["unresolved_incidents"]["caption"] = "Open incidents"

    if temp_alert_count == 1:
        default_cards["temp_alerts"]["caption"] = "Unread alert"
    else:
        default_cards["temp_alerts"]["caption"] = "Unread alerts"

    if unresolved_incident_count > 0:
        default_cards["unresolved_incidents"]["colour_class"] = "red"

    if temp_alert_count > 0:
        default_cards["temp_alerts"]["colour_class"] = "red"

    return default_cards


def get_end_shift_blocking_message(token):
    response = api_request(
        "GET",
        "/daily-shifts/current/fridge-temperature-progress",
        token=token,
    )

    if response is None:
        return "Unable to check checklist progress before ending the shift."

    if response.status_code != 200:
        return "Unable to check checklist progress before ending the shift."

    data = response.json()

    required_temperature_count = data.get("required_temperature_count", 0) or 0
    completed_temperature_count = data.get("completed_temperature_count", 0) or 0

    if required_temperature_count == 0:
        return None

    if completed_temperature_count < required_temperature_count:
        return "Unable to end shift due to incomplete checklist."

    return None


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


def render_daily_shift_action(token):
    shift_state = load_daily_shift_state(token)
    state = shift_state.get("state")

    if state == "active":
        if st.button("End Shift", use_container_width=True):
            blocking_message = get_end_shift_blocking_message(token)

            if blocking_message:
                st.session_state.show_end_shift_confirmation = False
                st.session_state.end_shift_block_message = blocking_message
                st.rerun()

            st.session_state.end_shift_block_message = None
            st.session_state.show_end_shift_confirmation = True
            st.rerun()

        return

    if state == "ended":
        st.button(
            "Start Shift",
            use_container_width=True,
            disabled=True,
            help="A shift with today's date has already ended.",
        )
        return

    if state == "no_shift_today":
        if st.button("Start Shift", use_container_width=True):
            st.session_state.end_shift_block_message = None
            response = api_request(
                "POST",
                "/daily-shifts/start",
                token=token,
            )

            if response and response.status_code == 200:
                st.success("Shift started.")
                st.rerun()

            if response is None:
                st.error(
                    "Unable to start shift.\n"
                    "The backend did not respond."
                )
            elif response.status_code != 200:
                detail = response.json().get("detail", "Unable to start shift.")
                st.info(detail)

        return

    st.error(shift_state.get("error", "Unable to load daily shift status."))


def render_end_shift_confirmation(token):
    block_message = st.session_state.get("end_shift_block_message")

    if block_message:
        st.error(block_message)
        return

    if not st.session_state.get("show_end_shift_confirmation"):
        return

    st.warning(
        "Ending the shift will close the current operational shift. "
        "Once ended, it cannot be restarted. A new shift can only be started "
        "on a different start date."
    )

    end_notes = st.text_area(
        "End-of-shift notes (optional)",
        key="daily_shift_end_notes",
    )

    confirm_col, cancel_col = st.columns(2)

    with confirm_col:
        if st.button("Confirm End Shift", use_container_width=True):
            response = api_request(
                "POST",
                "/daily-shifts/end",
                json={"end_notes": end_notes or None},
                token=token,
            )

            if response and response.status_code == 200:
                st.session_state.show_end_shift_confirmation = False
                st.session_state.end_shift_block_message = None
                st.session_state.pop("daily_shift_end_notes", None)
                st.success("Shift ended.")
                st.rerun()

            if response is None:
                st.error(
                    "Unable to end shift.\n"
                    "The backend did not respond."
                )
            elif response.status_code != 200:
                detail = response.json().get(
                    "detail",
                    "Unable to end shift.",
                )
                st.session_state.show_end_shift_confirmation = False
                st.session_state.end_shift_block_message = detail
                st.session_state.pop("daily_shift_end_notes", None)
                st.rerun()

    with cancel_col:
        if st.button("Cancel", use_container_width=True):
            st.session_state.show_end_shift_confirmation = False
            st.session_state.end_shift_block_message = None
            st.session_state.pop("daily_shift_end_notes", None)
            st.rerun()


def workflow_card_html(workflow_data):
    progress_percentage = int(max(0, min(workflow_data["progress_percentage"], 100)))
    progress_degrees = round(progress_percentage * 3.6)

    return f"""
        <div class="workflow-card">
            <div class="workflow-title">{escape(workflow_data["title"])}</div>
            <div class="donut" style="--progress: {progress_degrees}deg;">
                <div class="donut-inner">{progress_percentage}%</div>
            </div>
            <div class="workflow-value">{escape(workflow_data["main_value"])}</div>
            <div class="workflow-caption">{escape(workflow_data["caption"])}</div>
            <div class="workflow-caption">Status: {escape(workflow_data["status"])}</div>
        </div>
    """


def dummy_status_card_html(
    icon_label: str,
    title: str,
    value: str,
    caption: str,
    colour_class: str = "",
):
    colour_class = escape(colour_class)

    return f"""
        <div class="status-card {colour_class}">
            <div class="status-icon {colour_class}">{escape(icon_label)}</div>
            <div class="status-title">{escape(title)}</div>
            <div class="status-value {colour_class}">{escape(value)}</div>
            <div class="status-caption">{escape(caption)}</div>
        </div>
    """

def render_recent_activity_log():
    st.markdown(
        """
        <div style="
            border: 1px solid #334155;
            border-radius: 12px;
            background: #fff7ed;
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
            margin-top: 1rem;
            margin-bottom: 1rem;
        ">
            <div style="
                color: #f59e0b;
                font-size: 1.2rem;
                font-weight: 700;
                margin-bottom: 0.75rem;
            ">
                Recent Activity
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(height=320):
        for title, time_label, status in RECENT_ACTIVITY_ITEMS:
            if status == "alert":
                dot_background = "#ffe5e8"
                dot_colour = "#f04438"
            elif status == "warning":
                dot_background = "#fff1d6"
                dot_colour = "#f59e0b"
            else:
                dot_background = "#e8f8ee"
                dot_colour = "#079455"

            st.markdown(
                f"""
                <div style="
                    display: grid;
                    grid-template-columns: 42px 1fr;
                    column-gap: 0.9rem;
                    align-items: center;
                    padding: 0.6rem 0;
                ">
                    <div style="
                        width: 36px;
                        height: 36px;
                        border-radius: 50%;
                        background: {dot_background};
                        color: {dot_colour};
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        font-size: 0.68rem;
                        font-weight: 700;
                    ">
                        LOG
                    </div>
                    <div>
                        <div style="
                            color: #f8fafc;
                            font-size: 0.98rem;
                            font-weight: 500;
                            margin-bottom: 0.05rem;
                        ">
                            {escape(title)}
                        </div>
                        <div style="
                            color: #f59e0b;
                            font-size: 0.86rem;
                        ">
                            {escape(time_label)}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

def show():
    inject_dashboard_styles()

    if "show_recent_activity_log" not in st.session_state:
        st.session_state.show_recent_activity_log = False

    if "show_end_shift_confirmation" not in st.session_state:
        st.session_state.show_end_shift_confirmation = False
    if "end_shift_block_message" not in st.session_state:
        st.session_state.end_shift_block_message = None

    token = st.session_state.get("token")

    st.markdown('<div class="top-spacer"></div>', unsafe_allow_html=True)

    st.markdown(
        """
        <div class="quick-grid">
            <div class="quick-card">
                <div class="quick-card-icon">REP</div>
                <div class="quick-card-title">Equipment Repair<br>Log</div>
            </div>
            <div class="quick-card">
                <div class="quick-card-icon">SER</div>
                <div class="quick-card-title">Equipment<br>Service Records</div>
            </div>
            <div class="quick-card">
                <div class="quick-card-icon">ALG</div>
                <div class="quick-card-title">Allergen Matrix</div>
            </div>
            <div class="quick-card">
                <div class="quick-card-icon">SDR</div>
                <div class="quick-card-title">Special Dietary<br>Requirements<br>Choices</div>
            </div>
            <div class="quick-card">
                <div class="quick-card-icon">CLN</div>
                <div class="quick-card-title">Cleaning<br>Schedule</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    profile_progress = load_food_safety_profile_progress(token)
    fsms_progress = load_fsms_builder_progress(token)
    fsms_document_progress = (
        load_fsms_document_dashboard_progress(token)
    )
    fridge_temperature_progress = load_fridge_temperature_dashboard_progress(token)
    incident_summary_cards = load_daily_shift_incident_summary_cards(token)

    fridge_temperature_card = dummy_status_card_html(
        fridge_temperature_progress["icon_label"],
        fridge_temperature_progress["title"],
        fridge_temperature_progress["value"],
        fridge_temperature_progress["caption"],
        fridge_temperature_progress["colour_class"],
    )

    unresolved_incidents_card = dummy_status_card_html(
        incident_summary_cards["unresolved_incidents"]["icon_label"],
        incident_summary_cards["unresolved_incidents"]["title"],
        incident_summary_cards["unresolved_incidents"]["value"],
        incident_summary_cards["unresolved_incidents"]["caption"],
        incident_summary_cards["unresolved_incidents"]["colour_class"],
    )

    temp_alerts_card = dummy_status_card_html(
        incident_summary_cards["temp_alerts"]["icon_label"],
        incident_summary_cards["temp_alerts"]["title"],
        incident_summary_cards["temp_alerts"]["value"],
        incident_summary_cards["temp_alerts"]["caption"],
        incident_summary_cards["temp_alerts"]["colour_class"],
    )
    fsms_document_card = dummy_status_card_html(
        fsms_document_progress["icon_label"],
        fsms_document_progress["title"],
        fsms_document_progress["value"],
        fsms_document_progress["caption"],
        fsms_document_progress["colour_class"],
    )

    status_cards_html = f"""
        <div class="section-title"></div>
        <div class="status-grid">
            {workflow_card_html(profile_progress)}
            {workflow_card_html(fsms_progress)}
            {fsms_document_card}
            {fridge_temperature_card}
            {unresolved_incidents_card}
            {temp_alerts_card}
            {dummy_status_card_html("REP", "Repairs Logged", "3", "Open repair records")}
            {dummy_status_card_html("TRN", "Staff Trained", "4", "Trained today", "green")}
        </div>
    """

    st.markdown(status_cards_html, unsafe_allow_html=True)

    st.markdown('<div class="button-spacer"></div>', unsafe_allow_html=True)

    button_cols = st.columns(4, gap="medium")

    with button_cols[0]:
        if st.button("Recent Activity", use_container_width=True):
            st.session_state.show_recent_activity_log = (
                not st.session_state.show_recent_activity_log
            )

    with button_cols[1]:
        render_daily_shift_action(token)

    with button_cols[2]:
        st.button("Generate Report", use_container_width=True, disabled=True)

    with button_cols[3]:
        st.button("EHO Inspection Documentation", use_container_width=True, disabled=True)

    render_end_shift_confirmation(token)    

    if st.session_state.show_recent_activity_log:
        render_recent_activity_log()
