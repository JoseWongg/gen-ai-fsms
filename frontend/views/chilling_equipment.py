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
    return str(value).replace("_", " ").title()


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

    if submit_create_equipment(token, payload):
        st.rerun()


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

            if submit_update_equipment(token, equipment_id, payload):
                st.rerun()

        if equipment.get("is_active"):
            if st.button("Deactivate equipment", key=f"deactivate_{equipment_id}"):
                if submit_status_change(token, equipment_id, "deactivate"):
                    st.rerun()
        else:
            if st.button("Activate equipment", key=f"activate_{equipment_id}"):
                if submit_status_change(token, equipment_id, "activate"):
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

    equipment_items = load_chilling_equipment(token)
    if equipment_items is None:
        return

    render_create_form(token)

    st.divider()

    render_equipment_list(token, equipment_items)
