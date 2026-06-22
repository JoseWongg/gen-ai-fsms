import html

import streamlit as st

from shared import api_request
from views.checklist_tables import (
    CLEANING_SECTIONS,
    DELIVERY_TEMPERATURES_SECTIONS,
    FOOD_TEMPERATURES_SECTIONS,
    FRIDGE_TEMPERATURES_SECTION,
    OPERATIONAL_PROCEDURES_SECTIONS,
    TEMPERATURE_MONITORING_EQUIPMENT_VALIDATION_SECTIONS,
)


def inject_checklist_styles():
    st.markdown(
        """
        <style>
            div[data-baseweb="tab-list"] {
                flex-wrap: wrap;
                gap: 0.45rem;
                justify-content: center;
                overflow-x: visible;
                border-bottom: 0;
            }

            button[data-baseweb="tab"] {
                flex: 1 1 11.5rem;
                max-width: 15rem;
                min-height: 3rem;
                border: 1px solid rgba(148, 163, 184, 0.45);
                border-radius: 0.6rem;
                background: rgba(148, 163, 184, 0.12);
                padding: 0.45rem 0.6rem;
            }

            button[data-baseweb="tab"] p {
                white-space: normal;
                text-align: center;
                width: 100%;
                line-height: 1.15;
                font-size: 0.9rem;
            }

            button[data-baseweb="tab"][aria-selected="true"] {
                background: rgba(245, 158, 11, 0.18);
                border-color: rgba(245, 158, 11, 0.55);
                font-weight: 700;
            }

            div[data-baseweb="tab-highlight"],
            div[data-baseweb="tab-border"] {
                display: none;
            }

            .checklist-section-title {
                font-size: 1.05rem;
                font-weight: 700;
                margin-top: 1rem;
                margin-bottom: 0.4rem;
            }

            .checklist-table {
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 0.8rem;
            }

            .checklist-table th,
            .checklist-table td {
                border: 1px solid rgba(148, 163, 184, 0.45);
                padding: 0.45rem 0.6rem;
                vertical-align: top;
            }

            .checklist-table th {
                background: rgba(148, 163, 184, 0.18);
                font-weight: 700;
                text-align: center;
            }

            .checklist-table td {
                text-align: left;
                min-height: 1.5rem;
            }

            .checklist-placeholder {
                background: rgba(148, 163, 184, 0.12);
                border: 1px solid rgba(148, 163, 184, 0.35);
                padding: 0.75rem 1rem;
                border-radius: 0.35rem;
                margin-top: 0.5rem;
                margin-bottom: 1rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


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


def load_fridge_temperature_checks(token):
    if not token:
        return {
            "rows": [],
            "error": "Not signed in.",
        }

    response = api_request(
        "GET",
        "/daily-shifts/current/fridge-temperature-checks",
        token=token,
    )

    if response is None:
        return {
            "rows": [],
            "error": "Fridge temperature checks are unavailable.",
        }

    if response.status_code != 200:
        return {
            "rows": [],
            "error": f"Fridge temperature checks unavailable. HTTP {response.status_code}",
        }

    return {
        "rows": response.json(),
        "error": None,
    }


def format_temperature_value(value):
    if value is None:
        return ""

    return f"{value} C"


def render_shift_state_guard(shift_state):
    state = shift_state.get("state")

    if state == "active":
        return True

    if state in ("no_shift_today", "ended"):
        st.info("No active shift. Start a shift from the dashboard before completing the checklist.")
        return False

    st.error(shift_state.get("error", "Unable to load daily shift status."))
    return False


def render_html_table(columns, rows):
    display_rows = rows

    if not display_rows:
        display_rows = [["" for _column in columns]]

    header_cells = "".join(
        f"<th>{html.escape(str(column))}</th>"
        for column in columns
    )

    body = "".join(
        "<tr>"
        + "".join(
            f"<td>{html.escape(str(row[index])) if index < len(row) and row[index] is not None else ''}</td>"
            for index, _column in enumerate(columns)
        )
        + "</tr>"
        for row in display_rows
    )

    table_html = (
        '<table class="checklist-table">'
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table>"
    )

    st.markdown(table_html, unsafe_allow_html=True)


def render_section(section):
    st.markdown(
        f'<div class="checklist-section-title">{html.escape(section["title"])}</div>',
        unsafe_allow_html=True,
    )

    render_html_table(
        section.get("columns", []),
        section.get("rows", []),
    )


def render_sections(sections):
    for section in sections:
        render_section(section)


def render_fridge_temperatures_tab(token):
    section = FRIDGE_TEMPERATURES_SECTION
    result = load_fridge_temperature_checks(token)

    st.markdown(
        f'<div class="checklist-section-title">{html.escape(section["title"])}</div>',
        unsafe_allow_html=True,
    )

    if result["error"]:
        st.error(result["error"])
        return

    fridge_temperature_rows = [
        [
            row.get("equipment_name_snapshot", ""),
            row.get("equipment_type_snapshot", ""),
            format_temperature_value(row.get("am_temperature")),
            format_temperature_value(row.get("pm_temperature")),
        ]
        for row in result["rows"]
    ]

    render_html_table(
        section.get("columns", []),
        fridge_temperature_rows,
    )

    if not fridge_temperature_rows:
        st.markdown(
            """
            <div class="checklist-placeholder">
                No chilling equipment has been configured yet.
            </div>
            """,
            unsafe_allow_html=True,
        )


def show():
    inject_checklist_styles()

    st.title("Daily Shift Checklist")

    token = st.session_state.get("token")
    shift_state = load_daily_shift_state(token)

    if not render_shift_state_guard(shift_state):
        return

    tabs = st.tabs(
        [
            "Operational Procedures",
            "Temperature Monitoring Equipment Validation",
            "Fridge Temperatures",
            "Food Temperatures",
            "Delivery Temperatures",
            "Cleaning",
        ]
    )

    with tabs[0]:
        render_sections(OPERATIONAL_PROCEDURES_SECTIONS)

    with tabs[1]:
        render_sections(TEMPERATURE_MONITORING_EQUIPMENT_VALIDATION_SECTIONS)

    with tabs[2]:
        render_fridge_temperatures_tab(token)

    with tabs[3]:
        render_sections(FOOD_TEMPERATURES_SECTIONS)

    with tabs[4]:
        render_sections(DELIVERY_TEMPERATURES_SECTIONS)

    with tabs[5]:
        render_sections(CLEANING_SECTIONS)
