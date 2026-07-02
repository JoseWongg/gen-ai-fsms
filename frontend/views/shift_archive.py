from collections import defaultdict
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

SELECTED_ARCHIVE_SHIFT_ID_KEY = "selected_archive_shift_id"
SELECTED_ARCHIVE_VIEW_KEY = "selected_archive_view"
ARCHIVE_VIEW_CHECKLIST = "checklist"
ARCHIVE_VIEW_DIARY = "diary"


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


def format_equipment_value(value):
    labels = {
        "fridge": "Fridge",
        "freezer": "Freezer",
        "storage": "Storage",
        "display": "Display",
        "digital_or_dial_display": "Digital/dial display",
        "probe_between_packs": "Probe between packs",
    }

    return labels.get(value, format_text(value))


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
    return format_equipment_value(value)


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


def load_shift_diary_entries(token, shift_id):
    if not token:
        return None, "Not signed in."

    response = api_request(
        "GET",
        f"/daily-shifts/archive/{shift_id}/diary-entries",
        token=token,
    )

    if response is None:
        return None, "Shift diary entries are unavailable."

    if response.status_code != 200:
        return None, f"Shift diary entries unavailable. HTTP {response.status_code}"

    return response.json(), None


def render_temperature_record_block(title, temperature, recorded_by, recorded_at):
    st.markdown(f"**{title}**")
    st.markdown(format_temperature(temperature))
    st.caption(f"Recorded by: {format_text(recorded_by)}")
    st.caption(f"Recorded at: {format_datetime(recorded_at)}")


def render_read_only_fridge_temperature_records(records):
    if not records:
        st.info("No fridge/freezer temperature records were saved for this shift.")
        return

    for index, record in enumerate(records, start=1):
        asset_code = format_text(record.get("equipment_asset_code_snapshot"))
        equipment_name = format_text(record.get("equipment_name_snapshot"))

        title = f"{index}. {equipment_name} ({asset_code})"

        with st.expander(title, expanded=True):
            detail_columns = st.columns(3)

            with detail_columns[0]:
                st.markdown("**Use**")
                st.markdown(format_equipment_value(record.get("equipment_use_snapshot")))

            with detail_columns[1]:
                st.markdown("**Type**")
                st.markdown(format_equipment_value(record.get("equipment_type_snapshot")))

            with detail_columns[2]:
                st.markdown("**Check method**")
                st.markdown(format_temperature_method(record.get("temperature_check_method_snapshot")))

            st.divider()

            temperature_columns = st.columns(2)

            with temperature_columns[0]:
                render_temperature_record_block(
                    title="AM temperature",
                    temperature=record.get("am_temperature"),
                    recorded_by=record.get("am_recorded_by_name"),
                    recorded_at=record.get("am_recorded_at"),
                )

            with temperature_columns[1]:
                render_temperature_record_block(
                    title="PM temperature",
                    temperature=record.get("pm_temperature"),
                    recorded_by=record.get("pm_recorded_by_name"),
                    recorded_at=record.get("pm_recorded_at"),
                )


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


def find_shift_by_id(shifts, shift_id):
    for shift in shifts:
        if str(shift.get("id")) == str(shift_id):
            return shift

    return None


def clear_selected_archive_shift():
    st.session_state.pop(SELECTED_ARCHIVE_SHIFT_ID_KEY, None)
    st.session_state.pop(SELECTED_ARCHIVE_VIEW_KEY, None)


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


def toggle_archive_view(shift_id, requested_view):
    current_shift_id = st.session_state.get(SELECTED_ARCHIVE_SHIFT_ID_KEY)
    current_view = st.session_state.get(SELECTED_ARCHIVE_VIEW_KEY)

    st.session_state[SELECTED_ARCHIVE_SHIFT_ID_KEY] = shift_id

    if str(current_shift_id) == str(shift_id) and current_view == requested_view:
        st.session_state.pop(SELECTED_ARCHIVE_VIEW_KEY, None)
    else:
        st.session_state[SELECTED_ARCHIVE_VIEW_KEY] = requested_view

    st.rerun()


def render_shift_action_buttons(shift):
    shift_id = shift.get("id")

    button_columns = st.columns(2)

    with button_columns[0]:
        if st.button(
            "View diary",
            key=f"view_diary_{shift_id}",
            use_container_width=True,
        ):
            toggle_archive_view(
                shift_id=shift_id,
                requested_view=ARCHIVE_VIEW_DIARY,
            )

    with button_columns[1]:
        if st.button(
            "View checklist",
            key=f"view_checklist_{shift_id}",
            use_container_width=True,
        ):
            toggle_archive_view(
                shift_id=shift_id,
                requested_view=ARCHIVE_VIEW_CHECKLIST,
            )

def render_read_only_shift_diary_entries(entries):
    if not entries:
        st.info("No diary entries were recorded for this shift.")
        return

    for entry in entries:
        title = format_text(entry.get("title"))
        entry_text = format_text(entry.get("entry_text"))
        created_at = format_datetime(entry.get("created_at"))
        created_by = format_text(entry.get("created_by_name"))

        with st.expander(title, expanded=False):
            st.caption(f"Created at: {created_at}")
            st.caption(f"Created by: {created_by}")
            st.markdown(entry_text)


def render_shift_diary_detail(shift):
    st.markdown("### Diary entries")

    token = st.session_state.get("token")

    entries, error = load_shift_diary_entries(
        token=token,
        shift_id=shift.get("id"),
    )

    if error:
        st.error(error)
        return

    render_read_only_shift_diary_entries(entries)


def render_shift_checklist_detail(shift):
    st.markdown("### Checklist")
    st.markdown("#### Fridge/Freezer Temperatures")

    token = st.session_state.get("token")
    records, error = load_shift_fridge_temperature_records(
        token=token,
        shift_id=shift.get("id"),
    )

    if error:
        st.error(error)
        return

    render_read_only_fridge_temperature_records(records)


def render_selected_shift_detail(shift):
    if st.button("Back to archive"):
        clear_selected_archive_shift()
        st.rerun()

    st.title("Archived Shift Session")
    st.caption(
        "Read-only archive record for the selected shift session."
    )

    render_shift_details(shift)

    st.divider()

    render_shift_action_buttons(shift)

    selected_archive_view = st.session_state.get(SELECTED_ARCHIVE_VIEW_KEY)

    if selected_archive_view is None:
        st.info("Select View diary or View checklist to display archived shift records.")
        return

    st.divider()

    if selected_archive_view == ARCHIVE_VIEW_DIARY:
        render_shift_diary_detail(shift)
        return

    if selected_archive_view == ARCHIVE_VIEW_CHECKLIST:
        render_shift_checklist_detail(shift)
        return


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
        render_shift_action_buttons(shift)


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
                            render_shift_action_buttons(shift)


def show():
    token = st.session_state.get("token")

    selected_shift_id = st.session_state.get(SELECTED_ARCHIVE_SHIFT_ID_KEY)

    if selected_shift_id is not None:
        shifts, error = load_shift_archive(token=token)

        if error:
            st.error(error)
            return

        selected_shift = find_shift_by_id(shifts, selected_shift_id)

        if selected_shift is None:
            clear_selected_archive_shift()
            st.warning("The selected shift could not be found.")
        else:
            render_selected_shift_detail(selected_shift)
        return

    st.title("Shift Session Archive")

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
