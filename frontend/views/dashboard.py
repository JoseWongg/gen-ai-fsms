#import streamlit as st

#def show():
 #st.title("Dashboard")
    #st.write("Welcome to the main dashboard (work in progress).")


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

    status_cards_html = f"""
        <div class="section-title">Status Overview</div>
        <div class="status-grid">
            {workflow_card_html(profile_progress)}
            {workflow_card_html(fsms_progress)}
            {dummy_status_card_html("DAY", "Diary Completion", "75%", "Today's entries")}
            {dummy_status_card_html("TRN", "Staff Trained", "4", "Trained today", "green")}
            {dummy_status_card_html("INC", "Unresolved Incidents", "2", "Pending review")}
            {dummy_status_card_html("TMP", "Temp Alerts", "1", "Above safe limits", "red")}
            {dummy_status_card_html("REP", "Repairs Logged", "3", "Open repair records")}
            {dummy_status_card_html("DOC", "Documents Ready", "6", "Inspection documents")}
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
        st.button("End of Day", use_container_width=True, disabled=True)

    with button_cols[2]:
        st.button("Generate Report", use_container_width=True, disabled=True)

    with button_cols[3]:
        st.button("EHO Inspection Documentation", use_container_width=True, disabled=True)

    if st.session_state.show_recent_activity_log:
        render_recent_activity_log()