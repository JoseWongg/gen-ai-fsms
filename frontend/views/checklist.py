import streamlit as st


OPENING_PROCEDURES = [
    {"Opening procedures": "Turn on all lights", "sign": ""},
    {"Opening procedures": "Turn on gas and fans", "sign": ""},
    {"Opening procedures": "Turn on dishwasher", "sign": ""},
    {"Opening procedures": "Turn on equipment", "sign": ""},
    {"Opening procedures": "Set up and open kitchen", "sign": ""},
    {"Opening procedures": "Check prep list and 86 list", "sign": ""},
    {"Opening procedures": "Check booking for today", "sign": ""},
    {"Opening procedures": "Check in deliveries and put away", "sign": ""},
    {"Opening procedures": "Place any early orders", "sign": ""},
    {"Opening procedures": "Temperature checks", "sign": ""},
]

DURING_SERVICE_PROCEDURES = [
    {"During service procedures": "Maintain potwash area", "sign": ""},
    {"During service procedures": "Sweep floors", "sign": ""},
    {"During service procedures": "Clean as you go", "sign": ""},
]

END_OF_NIGHT_CLEANING_TASKS = [
    {"End of night cleaning tasks": "Fridges - top, front, handles, inside", "sign": ""},
    {"End of night cleaning tasks": "Freezer - top, front, handles", "sign": ""},
    {"End of night cleaning tasks": "Solid top - cleaned, including oven door", "sign": ""},
    {"End of night cleaning tasks": "Chargrill - scoured, drip tray wiped out", "sign": ""},
    {"End of night cleaning tasks": "Fryers - wipe and skim", "sign": ""},
    {"End of night cleaning tasks": "Workbench - cleaned, sanitized", "sign": ""},
    {"End of night cleaning tasks": "Shelves - clean and organized", "sign": ""},
    {"End of night cleaning tasks": "Microwaves - in and handles", "sign": ""},
    {"End of night cleaning tasks": "Bins - wipe over esp, where hands touch", "sign": ""},
    {"End of night cleaning tasks": "Dishwasher - in and out, handles, front", "sign": ""},
    {"End of night cleaning tasks": "Can opener, clean", "sign": ""},
]

CLOSING_DOWN_PROCEDURES = [
    {"Closing down procedures": "PM fridge temps", "sign": ""},
    {"Closing down procedures": "Turn off equipment", "sign": ""},
    {"Closing down procedures": "Turn off gas and fans", "sign": ""},
    {"Closing down procedures": "Clean and turn off dishwasher", "sign": ""},
    {"Closing down procedures": "Take out rubbish bags", "sign": ""},
    {"Closing down procedures": "Remove any items needed from freezer", "sign": ""},
    {"Closing down procedures": "Tidy any dishes that may be left", "sign": ""},
    {"Closing down procedures": "Double check fridge doors are shut", "sign": ""},
    {"Closing down procedures": "Request manager to check kitchen", "sign": ""},
    {"Closing down procedures": "Turn out lights", "sign": ""},
    {"Closing down procedures": "Lock kitchen", "sign": ""},
]

CLEANING_JOBS = [
    {"Cleaning Jobs to be completed today": "Morning shift", "signed": ""},
    {"Cleaning Jobs to be completed today": "Dry store - deep clean", "signed": ""},
    {"Cleaning Jobs to be completed today": "Fryers - filter and clean", "signed": ""},
    {"Cleaning Jobs to be completed today": "Insect Killer tray cleaned", "signed": ""},
]

FRIDGE_TEMPERATURES = [
    {
        "": "am",
        "F1": "",
        "F2": "",
        "F3": "",
        "F4": "",
        "F5": "",
        "Freezer 1": "",
        "Freezer 2": "",
        "Freezer 3": "",
    },
    {
        "": "pm",
        "F1": "",
        "F2": "",
        "F3": "",
        "F4": "",
        "F5": "",
        "Freezer 1": "",
        "Freezer 2": "",
        "Freezer 3": "",
    },
]

DELIVERY_TEMPS = [
    {"supplier": "", "product": "", "temp": ""},
    {"supplier": "", "product": "", "temp": ""},
    {"supplier": "", "product": "", "temp": ""},
    {"supplier": "", "product": "", "temp": ""},
]

PROBE_TEMPS = [
    {"Probe temps": "Probe 1", "boiling": "", "freezing": "", "signed": ""},
    {"Probe temps": "Probe 2", "boiling": "", "freezing": "", "signed": ""},
    {"Probe temps": "Probe 3", "boiling": "", "freezing": "", "signed": ""},
]

FOOD_PROBE_TEMPS = [
    {"name of dish": "", "temp": "", "action?": "", "signed": ""},
    {"name of dish": "", "temp": "", "action?": "", "signed": ""},
    {"name of dish": "", "temp": "", "action?": "", "signed": ""},
    {"name of dish": "", "temp": "", "action?": "", "signed": ""},
    {"name of dish": "", "temp": "", "action?": "", "signed": ""},
]

BATCH_COOKING = [
    {"Product": "", "temp": "", "time": "", "temp": "", "time ": ""},
    {"Product": "", "temp": "", "time": "", "temp": "", "time ": ""},
    {"Product": "", "temp": "", "time": "", "temp": "", "time ": ""},
    {"Product": "", "temp": "", "time": "", "temp": "", "time ": ""},
]


def inject_checklist_styles():
    st.markdown(
        """
        <style>
            .block-container {
                max-width: 1280px !important;
                padding-top: 1.5rem !important;
                padding-left: 1.5rem !important;
                padding-right: 1.5rem !important;
            }

            .checklist-header {
                border: 1px solid #d8e1ef;
                border-radius: 12px;
                background: #f8fafc;
                padding: 1rem 1.25rem;
                margin-bottom: 1rem;
            }

            .checklist-title {
                color: #0f172a;
                font-size: 1.5rem;
                font-weight: 700;
                margin-bottom: 0.25rem;
            }

            .checklist-subtitle {
                color: #475569;
                font-size: 0.92rem;
            }

            .dummy-note {
                color: #92400e;
                background: #fff7ed;
                border: 1px solid #fed7aa;
                border-radius: 10px;
                padding: 0.75rem 1rem;
                margin-bottom: 1rem;
                font-size: 0.9rem;
            }

            .checklist-section-title {
                color: #0f172a;
                font-size: 1rem;
                font-weight: 700;
                margin-top: 0.75rem;
                margin-bottom: 0.35rem;
            }

            .checklist-section-title.center {
                text-align: center;
            }

            .checklist-subsection-note {
                color: #475569;
                font-size: 0.85rem;
                margin-top: -0.2rem;
                margin-bottom: 0.35rem;
            }

            div[data-testid="stDataEditor"] {
                margin-bottom: 0.85rem;
            }

            div[data-testid="stButton"] > button {
                border: 1px solid #c7d2fe !important;
                border-radius: 10px !important;
                background: #eef4ff !important;
                color: #1e3a8a !important;
                font-weight: 700 !important;
                min-height: 42px !important;
            }

            @media (prefers-color-scheme: dark) {
                .checklist-header {
                    background: #111827;
                    border-color: #334155;
                }

                .checklist-title,
                .checklist-section-title {
                    color: #f8fafc;
                }

                .checklist-subtitle,
                .checklist-subsection-note {
                    color: #cbd5e1;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header():
    st.markdown(
        """
        <div class="checklist-header">
            <div class="checklist-title">Shift Management Checklist</div>
            <div class="checklist-subtitle">
                Dummy version of the kitchen opening, service, temperature, cleaning, prove-it and closing checklist.
            </div>
        </div>
        <div class="dummy-note">
            Dummy prototype view. Entries are currently for demonstration only and are not saved to the database.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_title(title, center=False):
    css_class = "checklist-section-title center" if center else "checklist-section-title"

    st.markdown(
        f'<div class="{css_class}">{title}</div>',
        unsafe_allow_html=True,
    )


def render_note(note):
    st.markdown(
        f'<div class="checklist-subsection-note">{note}</div>',
        unsafe_allow_html=True,
    )


def render_data_editor(data, key, height=None):
    st.data_editor(
        data,
        key=key,
        use_container_width=True,
        hide_index=True,
        height=height,
    )


def show():
    inject_checklist_styles()
    render_header()

    left_col, right_col = st.columns([1, 1.15], gap="large")

    with left_col:
        render_section_title("Opening procedures")
        render_data_editor(
            OPENING_PROCEDURES,
            key="opening_procedures_checklist",
            height=390,
        )

        render_section_title("During service procedures")
        render_data_editor(
            DURING_SERVICE_PROCEDURES,
            key="during_service_procedures_checklist",
            height=165,
        )

        render_section_title("End of night cleaning tasks")
        render_data_editor(
            END_OF_NIGHT_CLEANING_TASKS,
            key="end_of_night_cleaning_tasks_checklist",
            height=420,
        )

        render_section_title("Closing down procedures")
        render_data_editor(
            CLOSING_DOWN_PROCEDURES,
            key="closing_down_procedures_checklist",
            height=420,
        )

        render_section_title("Cleaning Jobs to be completed today")
        render_section_title("Morning shift", center=True)
        render_data_editor(
            CLEANING_JOBS[1:],
            key="cleaning_jobs_checklist",
            height=165,
        )

    with right_col:
        render_section_title("Fridge Temperatures", center=True)
        render_data_editor(
            FRIDGE_TEMPERATURES,
            key="fridge_temperatures_checklist",
            height=120,
        )

        render_section_title("Delivery temps", center=True)
        render_data_editor(
            DELIVERY_TEMPS,
            key="delivery_temps_checklist",
            height=205,
        )

        render_section_title("Probe temps")
        render_data_editor(
            PROBE_TEMPS,
            key="probe_temps_checklist",
            height=165,
        )

        render_section_title("food probe temps")
        render_data_editor(
            FOOD_PROBE_TEMPS,
            key="food_probe_temps_checklist",
            height=245,
        )

        render_section_title("Batch cooking (batch items must cooled under 90 mins)")
        render_data_editor(
            BATCH_COOKING,
            key="batch_cooking_checklist",
            height=205,
        )

    st.divider()

    button_cols = st.columns(4, gap="medium")

    with button_cols[0]:
        st.button("Save Checklist", use_container_width=True, disabled=True)

    with button_cols[1]:
        st.button("Submit Shift", use_container_width=True, disabled=True)

    with button_cols[2]:
        st.button("Export PDF", use_container_width=True, disabled=True)

    with button_cols[3]:
        st.button("Manager Review", use_container_width=True, disabled=True)

    st.caption("Buttons are disabled because this is a dummy prototype view.")