from datetime import datetime

import streamlit as st

from shared import api_request


EQUIPMENT_USE_OPTIONS = [
    "storage",
    "display",
]

EQUIPMENT_TYPE_OPTIONS = [
    "fridge",
    "freezer",
]

TEMPERATURE_CHECK_METHOD_OPTIONS = [
    "digital_or_dial_display",
    "probe_between_packs",
]


def format_option(value):
    if not value:
        return ""

    labels = {
        "fridge": "Fridge",
        "freezer": "Freezer",
        "storage": "Storage",
        "display": "Display",
        "digital_or_dial_display": "Digital/dial display",
        "probe_between_packs": "Probe between packs",
        "active": "Active",
        "ended": "Ended",
    }

    return labels.get(value, str(value).replace("_", " ").title())


def format_datetime(value):
    if not value:
        return "No data yet"

    try:
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return str(value)


def format_date(value):
    if not value:
        return "No data yet"

    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return parsed.strftime("%d-%m-%Y")
    except ValueError:
        return str(value)


def format_temperature(value):
    if value is None or value == "":
        return "No data yet"

    return f"{value} degrees C"


def format_text(value):
    if value is None or value == "":
        return "No data yet"

    return str(value)


def options_with_current(options, current_value):
    values = list(options)
    if current_value and current_value not in values:
        values.append(current_value)
    return values


def show_api_error(response, fallback_message):
    if response is None:
        st.error(fallback_message)
        return

    try:
        detail = response.json().get("detail")
    except Exception:
        detail = None

    st.error(detail or fallback_message)


def load_chilling_equipment(token):
    response = api_request(
        "GET",
        "/chilling-equipment/",
        token=token,
    )

    if response is None or response.status_code != 200:
        show_api_error(response, "Unable to load chilling equipment.")
        return None

    return response.json()


def load_chilling_equipment_temperature_records(token, equipment_id):
    response = api_request(
        "GET",
        f"/chilling-equipment/{equipment_id}/temperature-history",
        token=token,
    )

    if response is None or response.status_code != 200:
        show_api_error(response, "Unable to load chilling equipment temperature records.")
        return None

    return response.json()


def submit_create_equipment(token, payload):
    response = api_request(
        "POST",
        "/chilling-equipment/",
        json=payload,
        token=token,
    )

    if response is None or response.status_code not in (200, 201):
        show_api_error(response, "Unable to create chilling equipment.")
        return False

    st.success("Chilling equipment added.")
    return True


def submit_update_equipment(token, equipment_id, payload):
    response = api_request(
        "PATCH",
        f"/chilling-equipment/{equipment_id}",
        json=payload,
        token=token,
    )

    if response is None or response.status_code != 200:
        show_api_error(response, "Unable to update chilling equipment.")
        return False

    st.success("Chilling equipment updated.")
    return True


def submit_status_change(token, equipment_id, action):
    response = api_request(
        "PATCH",
        f"/chilling-equipment/{equipment_id}/{action}",
        token=token,
    )

    if response is None or response.status_code != 200:
        show_api_error(response, f"Unable to {action} chilling equipment.")
        return False

    if action == "activate":
        st.success("Chilling equipment activated.")
    else:
        st.success("Chilling equipment deactivated.")

    return True


PENDING_EQUIPMENT_CHANGE_KEY = "pending_chilling_equipment_change"
TEMPERATURE_RECORDS_VISIBILITY_PREFIX = "show_chilling_equipment_temperature_records_"

EQUIPMENT_CHANGE_WARNINGS = {
    "create": (
        "This will add the equipment to Food Safety > Approved Methods and to "
        "Fridge Temperatures checklist rows where applicable. Historical shift "
        "records will not be changed."
    ),
    "update": (
        "This will update the equipment shown in Food Safety > Approved Methods. "
        "If the current shift checklist already has this equipment, its existing "
        "row details will not be changed. The updated details will apply to "
        "future shift checklist rows. Historical shift records will not be changed."
    ),
    "deactivate": (
        "This will remove the equipment from Food Safety > Approved Methods and "
        "from active and future Fridge Temperatures checklist rows. Historical "
        "shift records will not be changed."
    ),
    "activate": (
        "This will add the equipment back to Food Safety > Approved Methods and "
        "to Fridge Temperatures checklist rows where applicable. Historical shift "
        "records will not be changed."
    ),
}


def get_equipment_change_warning(action):
    return EQUIPMENT_CHANGE_WARNINGS.get(
        action,
        (
            "This change may affect Food Safety > Approved Methods and "
            "Fridge Temperatures checklist rows. Historical shift records "
            "will not be changed."
        ),
    )


def set_pending_equipment_change(action, label, equipment_id=None, payload=None):
    st.session_state[PENDING_EQUIPMENT_CHANGE_KEY] = {
        "action": action,
        "label": label,
        "equipment_id": equipment_id,
        "payload": payload,
    }


def clear_pending_equipment_change():
    st.session_state.pop(PENDING_EQUIPMENT_CHANGE_KEY, None)


def render_pending_equipment_change(token):
    pending_change = st.session_state.get(PENDING_EQUIPMENT_CHANGE_KEY)

    if not pending_change:
        return False

    st.warning(get_equipment_change_warning(pending_change.get("action")))
    st.caption(f"Pending change: {pending_change.get('label')}")

    continue_col, cancel_col = st.columns(2)

    with continue_col:
        if st.button(
            "Continue and save change",
            key="continue_chilling_equipment_change",
        ):
            action = pending_change.get("action")
            equipment_id = pending_change.get("equipment_id")
            payload = pending_change.get("payload") or {}

            if action == "create":
                success = submit_create_equipment(token, payload)
            elif action == "update":
                success = submit_update_equipment(token, equipment_id, payload)
            elif action in ("activate", "deactivate"):
                success = submit_status_change(token, equipment_id, action)
            else:
                st.error("Unknown chilling equipment change.")
                return True

            if success:
                clear_pending_equipment_change()
                st.rerun()

    with cancel_col:
        if st.button(
            "Cancel change",
            key="cancel_chilling_equipment_change",
        ):
            clear_pending_equipment_change()
            st.info("Change cancelled.")
            st.rerun()

    return True


def render_create_form(token):
    st.subheader("Add chilling equipment")

    with st.form("create_chilling_equipment_form"):
        equipment_name = st.text_input("Equipment name *")
        equipment_use = st.selectbox(
            "Equipment use *",
            options=EQUIPMENT_USE_OPTIONS,
            format_func=format_option,
        )
        equipment_type = st.selectbox(
            "Equipment type *",
            options=EQUIPMENT_TYPE_OPTIONS,
            format_func=format_option,
        )
        temperature_check_method = st.selectbox(
            "Temperature check method *",
            options=TEMPERATURE_CHECK_METHOD_OPTIONS,
            format_func=format_option,
        )

        submitted = st.form_submit_button("Add equipment")

    if not submitted:
        return

    if not equipment_name.strip():
        st.error("Equipment name is required.")
        return

    payload = {
        "source_safety_point_id": "manual-admin-setup",
        "equipment_name": equipment_name.strip(),
        "equipment_use": equipment_use,
        "equipment_type": equipment_type,
        "temperature_check_method": temperature_check_method,
    }

    set_pending_equipment_change(
        action="create",
        label=f"Add {equipment_name.strip()}",
        payload=payload,
    )
    st.rerun()


def render_temperature_record_block(title, temperature, recorded_by, recorded_at):
    st.markdown(f"**{title}**")
    st.markdown(format_temperature(temperature))
    st.caption(f"Recorded by: {format_text(recorded_by)}")
    st.caption(f"Recorded at: {format_datetime(recorded_at)}")


def render_equipment_temperature_records(records):
    if not records:
        st.info("No temperature records have been saved for this equipment yet.")
        return

    for record in records:
        shift_label = (
            f"{format_date(record.get('shift_date'))} "
            f"({format_option(record.get('shift_status'))})"
        )

        st.markdown(f"##### Shift: {shift_label}")

        snapshot_columns = st.columns(3)

        with snapshot_columns[0]:
            st.markdown("**Use**")
            st.markdown(format_option(record.get("equipment_use_snapshot")))

        with snapshot_columns[1]:
            st.markdown("**Type**")
            st.markdown(format_option(record.get("equipment_type_snapshot")))

        with snapshot_columns[2]:
            st.markdown("**Check method**")
            st.markdown(format_option(record.get("temperature_check_method_snapshot")))

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

        st.divider()


def render_equipment_action_buttons(token, equipment):
    equipment_id = equipment.get("id")
    records_visibility_key = f"{TEMPERATURE_RECORDS_VISIBILITY_PREFIX}{equipment_id}"
    records_visible = st.session_state.get(records_visibility_key, False)

    temperature_label = (
        "Hide temperature records"
        if records_visible
        else "Temperature records"
    )

    temperature_col, change_col, status_col = st.columns(3)

    with temperature_col:
        if st.button(
            temperature_label,
            key=f"temperature_records_{equipment_id}",
            use_container_width=True,
        ):
            st.session_state[records_visibility_key] = not records_visible
            st.rerun()

    with change_col:
        st.button(
            "Change records",
            key=f"change_records_{equipment_id}",
            use_container_width=True,
            disabled=True,
            help="Change records will be added next.",
        )

    with status_col:
        if equipment.get("is_active"):
            if st.button(
                "Deactivate equipment",
                key=f"deactivate_{equipment_id}",
                use_container_width=True,
            ):
                set_pending_equipment_change(
                    action="deactivate",
                    label=f"Deactivate {equipment.get('equipment_name') or 'this equipment'}",
                    equipment_id=equipment_id,
                )
                st.rerun()
        else:
            if st.button(
                "Activate equipment",
                key=f"activate_{equipment_id}",
                use_container_width=True,
            ):
                set_pending_equipment_change(
                    action="activate",
                    label=f"Activate {equipment.get('equipment_name') or 'this equipment'}",
                    equipment_id=equipment_id,
                )
                st.rerun()

    if not st.session_state.get(records_visibility_key, False):
        return

    records = load_chilling_equipment_temperature_records(token, equipment_id)

    if records is None:
        return

    st.markdown("#### Temperature records")
    render_equipment_temperature_records(records)


def render_equipment_editor(token, equipment):
    equipment_id = equipment.get("id")
    status_label = "Active" if equipment.get("is_active") else "Inactive"
    asset_code = equipment.get("equipment_asset_code") or "No asset code"

    title = (
        f"{equipment.get('equipment_name') or 'Unnamed equipment'} "
        f"({asset_code}) - {status_label}"
    )

    with st.expander(title, expanded=False):
        st.caption(f"Asset code: {asset_code}")

        render_equipment_action_buttons(token, equipment)

        st.divider()

        with st.form(f"edit_chilling_equipment_{equipment_id}"):
            equipment_name = st.text_input(
                "Equipment name *",
                value=equipment.get("equipment_name") or "",
                key=f"equipment_name_{equipment_id}",
            )

            use_options = options_with_current(
                EQUIPMENT_USE_OPTIONS,
                equipment.get("equipment_use"),
            )
            type_options = options_with_current(
                EQUIPMENT_TYPE_OPTIONS,
                equipment.get("equipment_type"),
            )
            method_options = options_with_current(
                TEMPERATURE_CHECK_METHOD_OPTIONS,
                equipment.get("temperature_check_method"),
            )

            equipment_use = st.selectbox(
                "Equipment use *",
                options=use_options,
                index=use_options.index(equipment.get("equipment_use"))
                if equipment.get("equipment_use") in use_options
                else 0,
                format_func=format_option,
                key=f"equipment_use_{equipment_id}",
            )

            equipment_type = st.selectbox(
                "Equipment type *",
                options=type_options,
                index=type_options.index(equipment.get("equipment_type"))
                if equipment.get("equipment_type") in type_options
                else 0,
                format_func=format_option,
                key=f"equipment_type_{equipment_id}",
            )

            temperature_check_method = st.selectbox(
                "Temperature check method *",
                options=method_options,
                index=method_options.index(equipment.get("temperature_check_method"))
                if equipment.get("temperature_check_method") in method_options
                else 0,
                format_func=format_option,
                key=f"temperature_check_method_{equipment_id}",
            )

            submitted = st.form_submit_button("Save changes")

        if submitted:
            if not equipment_name.strip():
                st.error("Equipment name is required.")
                return

            payload = {
                "source_safety_point_id": equipment.get("source_safety_point_id"),
                "equipment_name": equipment_name.strip(),
                "equipment_use": equipment_use,
                "equipment_type": equipment_type,
                "temperature_check_method": temperature_check_method,
            }

            set_pending_equipment_change(
                action="update",
                label=f"Update {equipment_name.strip()}",
                equipment_id=equipment_id,
                payload=payload,
            )
            st.rerun()



def render_equipment_list(token, equipment_items):
    st.subheader("Current chilling equipment")

    if not equipment_items:
        st.info("No chilling equipment has been configured yet.")
        return

    active_count = sum(1 for item in equipment_items if item.get("is_active"))
    inactive_count = len(equipment_items) - active_count

    st.caption(
        f"{active_count} active item(s), {inactive_count} inactive item(s). "
        "Only active equipment is used for future shift checklist rows."
    )

    for equipment in equipment_items:
        render_equipment_editor(token, equipment)


def show():
    st.title("Chilling Equipment")

    user = st.session_state.get("user")
    if not user or user.get("role") != "admin":
        st.error("You must be an admin to access Chilling Equipment setup.")
        return

    token = st.session_state.get("token")
    if not token:
        st.error("You must be logged in to manage chilling equipment.")
        return

    st.info(
        "Manage the chilling equipment used by the Food Safety Management System "
        "and future daily shift checklist rows. Historical shift records keep their "
        "original equipment snapshots."
    )

    if render_pending_equipment_change(token):
        return

    equipment_items = load_chilling_equipment(token)
    if equipment_items is None:
        return

    render_create_form(token)

    st.divider()

    render_equipment_list(token, equipment_items)
