import html
from decimal import Decimal, InvalidOperation

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

            div[data-testid="stTextInput"] input {
                text-align: center;
            }

            .temperature-row-card {
                border: 1px solid rgba(148, 163, 184, 0.35);
                border-radius: 0.5rem;
                padding: 0.75rem 0.85rem;
                margin-bottom: 0.75rem;
                background: rgba(148, 163, 184, 0.06);
            }

            .temperature-row-title {
                font-weight: 700;
                margin-bottom: 0.2rem;
            }

            .temperature-row-type {
                color: #64748b;
                font-size: 0.9rem;
                margin-bottom: 0.35rem;
                text-align: center;
            }

            .temperature-header-spacer {
                height: 0.7rem;
            }

            .temperature-list-spacer {
                height: 0.45rem;
            }

            .temperature-group-header {
                text-align: center;
                font-weight: 700;
            }

            .temperature-entry-status {
                font-size: 0.8rem;
                text-align: center;
                margin-top: 0.15rem;
                margin-bottom: 0.35rem;
            }

            .temperature-entry-status.saved {
                color: #16a34a;
                font-weight: 600;
            }

            .temperature-entry-status.unsaved {
                color: #f59e0b;
                font-weight: 600;
            }

            .temperature-entry-status.empty {
                color: #64748b;
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


def save_fridge_temperature_check(token, check_id, payload):
    response = api_request(
        "PATCH",
        f"/daily-shifts/current/fridge-temperature-checks/{check_id}",
        json=payload,
        token=token,
    )

    if response is None:
        return False, "Fridge temperature check could not be saved."

    if response.status_code != 200:
        return False, f"Fridge temperature check could not be saved. HTTP {response.status_code}"

    return True, "Temperature change saved."


def format_temperature_input(value):
    if value is None:
        return ""

    return str(value)


def validate_temperature_input(value):
    cleaned_value = value.strip()

    if not cleaned_value:
        return None, "Enter a temperature value before saving."

    try:
        float(cleaned_value)
    except ValueError:
        return None, "Enter a valid number."

    return cleaned_value, None


def rerun_checklist_page():
    return None


def normalise_temperature_for_comparison(value):
    if value is None:
        return None

    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None


def render_temperature_status(saved_value, current_value, recorded_at):
    current_text = current_value.strip()

    if saved_value is None and not current_text:
        return

    saved_number = normalise_temperature_for_comparison(saved_value)
    current_number = normalise_temperature_for_comparison(current_text)

    if saved_value is None and current_text:
        status_text = "Unsaved changes"
        status_class = "unsaved"
    elif (
        saved_number is not None
        and current_number is not None
        and saved_number == current_number
        and recorded_at is not None
    ):
        status_text = "Saved"
        status_class = "saved"
    else:
        status_text = "Unsaved changes"
        status_class = "unsaved"

    st.markdown(
        f'<div class="temperature-entry-status {status_class}">{html.escape(status_text)}</div>',
        unsafe_allow_html=True,
    )


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

    st.markdown('<div class="temperature-header-spacer"></div>', unsafe_allow_html=True)

    if result["error"]:
        st.error(result["error"])
        return

    rows = result["rows"]

    if not rows:
        render_html_table(
            section.get("columns", []),
            [],
        )

        st.markdown(
            """
            <div class="checklist-placeholder">
                No chilling equipment has been configured yet.
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    header_columns = st.columns([2, 1, 2.35, 0.25, 2.35])
    header_columns[0].markdown('<div class="temperature-group-header">Name</div>', unsafe_allow_html=True)
    header_columns[1].markdown('<div class="temperature-group-header">Type</div>', unsafe_allow_html=True)
    header_columns[2].markdown('<div class="temperature-group-header">AM</div>', unsafe_allow_html=True)
    header_columns[4].markdown('<div class="temperature-group-header">PM</div>', unsafe_allow_html=True)

    st.markdown('<div class="temperature-list-spacer"></div>', unsafe_allow_html=True)

    for row in rows:
        check_id = row["id"]
        row_columns = st.columns([2, 1, 2.35, 0.25, 2.35])

        with row_columns[0]:
            st.write(row.get("equipment_name_snapshot", ""))

        with row_columns[1]:
            st.markdown(
                f'<div class="temperature-row-type">{html.escape(row.get("equipment_type_snapshot", ""))}</div>',
                unsafe_allow_html=True,
            )

        with row_columns[2]:
            am_columns = st.columns([1.65, 1], gap="small")

            am_value = am_columns[0].text_input(
                "AM",
                value=format_temperature_input(row.get("am_temperature")),
                key=f"am_temperature_{check_id}",
                label_visibility="collapsed",
            )

            am_saved_value = row.get("am_temperature")
            am_recorded_at = row.get("am_recorded_at")

            if am_columns[1].button(
                "Save",
                key=f"save_am_temperature_{check_id}",
                use_container_width=True,
            ):
                temperature_value, validation_error = validate_temperature_input(am_value)

                if validation_error:
                    st.error(validation_error)
                else:
                    saved, message = save_fridge_temperature_check(
                        token=token,
                        check_id=check_id,
                        payload={"am_temperature": temperature_value},
                    )

                    if saved:
                        am_saved_value = temperature_value
                        am_recorded_at = "saved"
                        st.success(message)
                    else:
                        st.error(message)

            render_temperature_status(
                saved_value=am_saved_value,
                current_value=am_value,
                recorded_at=am_recorded_at,
            )

        with row_columns[4]:
            pm_columns = st.columns([1.65, 1], gap="small")

            pm_value = pm_columns[0].text_input(
                "PM",
                value=format_temperature_input(row.get("pm_temperature")),
                key=f"pm_temperature_{check_id}",
                label_visibility="collapsed",
            )

            pm_saved_value = row.get("pm_temperature")
            pm_recorded_at = row.get("pm_recorded_at")

            if pm_columns[1].button(
                "Save",
                key=f"save_pm_temperature_{check_id}",
                use_container_width=True,
            ):
                temperature_value, validation_error = validate_temperature_input(pm_value)

                if validation_error:
                    st.error(validation_error)
                else:
                    saved, message = save_fridge_temperature_check(
                        token=token,
                        check_id=check_id,
                        payload={"pm_temperature": temperature_value},
                    )

                    if saved:
                        pm_saved_value = temperature_value
                        pm_recorded_at = "saved"
                        st.success(message)
                    else:
                        st.error(message)

            render_temperature_status(
                saved_value=pm_saved_value,
                current_value=pm_value,
                recorded_at=pm_recorded_at,
            )

        st.divider()


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
