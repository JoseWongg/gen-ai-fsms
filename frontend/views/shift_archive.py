from collections import defaultdict
import html
from datetime import date, datetime

import streamlit as st

from shared import api_request


MONTH_NAMES = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def format_date(value):
    if not value:
        return "No data yet"

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return parsed.strftime("%d-%m-%Y")
    except ValueError:
        return value


def format_datetime(value):
    if not value:
        return "No data yet"

    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return value


def format_text(value):
    if value is None or value == "":
        return "No data yet"

    return str(value)


def format_status(value):
    if value == "active":
        return "Active"

    if value == "ended":
        return "Ended"

    return format_text(value)


def load_shift_archive(token, selected_date=None):
    if not token:
        return None, "Not signed in."

    endpoint = "/daily-shifts/archive"

    if selected_date is not None:
        endpoint = f"{endpoint}?shift_date={selected_date.isoformat()}"

    response = api_request(
        "GET",
        endpoint,
        token=token,
    )

    if response is None:
        return None, "Daily shift archive is unavailable."

    if response.status_code != 200:
        return None, f"Daily shift archive unavailable. HTTP {response.status_code}"

    return response.json(), None


def format_temperature(value):
    if value is None or value == "":
        return "No data yet"

    return f"{value} degrees C"


def format_temperature_method(value):
    method_labels = {
        "digital_or_dial_display": "Digital/dial display",
        "probe_between_packs": "Probe between packs",
    }

    return method_labels.get(value, format_text(value))


def load_shift_fridge_temperature_records(token, shift_id):
    if not token:
        return None, "Not signed in."

    response = api_request(
        "GET",
        f"/daily-shifts/archive/{shift_id}/fridge-temperature-checks",
        token=token,
    )

    if response is None:
        return None, "Fridge temperature records are unavailable."

    if response.status_code != 200:
        return None, f"Fridge temperature records unavailable. HTTP {response.status_code}"

    return response.json(), None


def render_read_only_fridge_temperature_records(records):
    if not records:
        st.info("No fridge/freezer temperature records were saved for this shift.")
        return

    columns = [
        "Equipment",
        "Use",
        "Type",
        "Check method",
        "AM temperature",
        "AM recorded by",
        "AM recorded at",
        "PM temperature",
        "PM recorded by",
        "PM recorded at",
    ]

    table_rows = []

    for record in records:
        table_rows.append(
            [
                format_text(record.get("equipment_name_snapshot")),
                format_text(record.get("equipment_use_snapshot")),
                format_text(record.get("equipment_type_snapshot")),
                format_temperature_method(record.get("temperature_check_method_snapshot")),
                format_temperature(record.get("am_temperature")),
                format_text(record.get("am_recorded_by_name")),
                format_datetime(record.get("am_recorded_at")),
                format_temperature(record.get("pm_temperature")),
                format_text(record.get("pm_recorded_by_name")),
                format_datetime(record.get("pm_recorded_at")),
            ]
        )

    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = "\n".join(
        "| " + " | ".join(html.escape(str(value)) for value in row) + " |"
        for row in table_rows
    )

    st.markdown(header + "\n" + separator + "\n" + body)


def group_shifts_by_year_month(shifts):
    grouped = defaultdict(lambda: defaultdict(list))

    for shift in shifts:
        shift_date = shift.get("shift_date")

        try:
            parsed_date = datetime.strptime(shift_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            continue

        grouped[parsed_date.year][parsed_date.month].append(shift)

    return grouped


def render_shift_details(shift):
    st.markdown("#### Shift details")

    detail_rows = [
        ("Status", format_status(shift.get("status"))),
        ("Shift date", format_date(shift.get("shift_date"))),
        ("Started by", format_text(shift.get("started_by_name"))),
        ("Started at", format_datetime(shift.get("started_at"))),
        ("Ended by", format_text(shift.get("ended_by_name"))),
        ("Ended at", format_datetime(shift.get("ended_at"))),
        ("Closing notes", format_text(shift.get("end_notes"))),
    ]

    for label, value in detail_rows:
        st.markdown(f"**{label}:** {value}")


def render_shift_checklist_preview(shift):
    shift_id = shift.get("id")
    selected_key = f"show_shift_checklist_{shift_id}"

    if st.button(
        "View checklist",
        key=f"view_checklist_{shift_id}",
        use_container_width=True,
    ):
        st.session_state[selected_key] = not st.session_state.get(selected_key, False)

    if st.session_state.get(selected_key):
        st.markdown("#### Checklist")
        st.markdown("##### Fridge/Freezer Temperatures")

        token = st.session_state.get("token")
        records, error = load_shift_fridge_temperature_records(
            token=token,
            shift_id=shift_id,
        )

        if error:
            st.error(error)
            return

        render_read_only_fridge_temperature_records(records)


def render_filtered_archive(shifts):
    if not shifts:
        st.info("No shift sessions found.")
        return

    for shift in shifts:
        title = (
            f"{format_date(shift.get('shift_date'))} "
            f"({format_status(shift.get('status'))})"
        )

        st.markdown(f"### {title}")
        render_shift_details(shift)
        render_shift_checklist_preview(shift)


def render_archive(shifts):
    if not shifts:
        st.info("No shift sessions found.")
        return

    grouped = group_shifts_by_year_month(shifts)

    for year in sorted(grouped.keys(), reverse=True):
        with st.expander(str(year), expanded=False):
            months = grouped[year]

            for month in sorted(months.keys(), reverse=True):
                month_label = MONTH_NAMES.get(month, str(month))

                with st.expander(month_label, expanded=False):
                    sorted_shifts = sorted(
                        months[month],
                        key=lambda item: (
                            item.get("shift_date") or "",
                            item.get("started_at") or "",
                        ),
                        reverse=True,
                    )

                    for shift in sorted_shifts:
                        title = (
                            f"{format_date(shift.get('shift_date'))} "
                            f"({format_status(shift.get('status'))})"
                        )

                        with st.expander(title):
                            render_shift_details(shift)
                            render_shift_checklist_preview(shift)


def show():
    st.title("Shift Session Archive")

    token = st.session_state.get("token")

    st.caption(
        "View current and historical shift sessions for this business profile."
    )

    use_date_filter = st.checkbox("Filter by shift date")

    selected_date = None

    if use_date_filter:
        selected_date = st.date_input(
            "Shift date",
            value=date.today(),
            format="DD-MM-YYYY",
        )

    shifts, error = load_shift_archive(
        token=token,
        selected_date=selected_date,
    )

    if error:
        st.error(error)
        return

    if use_date_filter:
        render_filtered_archive(shifts)
        return

    render_archive(shifts)
