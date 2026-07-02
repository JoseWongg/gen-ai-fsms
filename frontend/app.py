import streamlit as st
from views import chilling_equipment as chilling_equipment_page
import streamlit_antd_components as sac

from shared import api_request

from views.login import show as login_page
from views.register import show as register_page
from views.dashboard import show as dashboard_page
from views.admin import show as admin_page
from views.forgot import show as forgot_page
from views.reset_password import show as reset_page
from views.onboarding_screening import show as screening_page
from views.onboarding_approval import show as approval_page
from views.approved_methods import show as approved_methods_page
from views.checklist import show as checklist_page
from views.shift_archive import show as shift_archive_page
from views.shift_diary import show as shift_diary_page
from views.notifications import show as notifications_page

# If a reset token is present in the URL, show the reset page immediately.
query_params = st.query_params
if "token" in query_params:
    reset_page()
    st.stop()


# Initialise session state.
if "token" not in st.session_state:
    st.session_state.token = None

if "user" not in st.session_state:
    st.session_state.user = None

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "page" not in st.session_state:
    st.session_state.page = "landing"


def landing():
    col_spacer, col_btn1, col_btn2 = st.columns([4, 1, 1])

    with col_btn1:
        if st.button("Login", width="stretch"):
            st.session_state.page = "login"
            st.rerun()

    with col_btn2:
        if st.button("Register", width="stretch"):
            st.session_state.page = "register"
            st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    col1, col_img, col2 = st.columns([1, 2, 1])

    with col_img:
        st.image("assets/images/landing_1.png", width="stretch", caption="")

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(
        """
        <div style="text-align: center;">
            <h1>Welcome to Gen-AI Food Safety Management</h1>
            <p style="font-size:1.2rem;">Your intelligent assistant for food safety compliance.</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def logout():
    screening_state_keys = (
        "screening_session",
        "screening_messages",
        "screening_complete",
        "screening_just_completed",
        "screening_processing",
        "pending_screening_answer",
        "screening_ephemeral_status",
        "screening_ephemeral_after_index",
        "screening_chat_input",
    )

    for key in screening_state_keys:
        st.session_state.pop(key, None)

    st.session_state.token = None
    st.session_state.user = None
    st.session_state.authenticated = False
    st.session_state.page = "landing"
    st.rerun()


def is_admin():
    user = st.session_state.get("user") or {}
    return user.get("role") == "admin"


def show_placeholder(title, message=None):
    st.title(title)

    if message:
        st.info(message)
    else:
        st.info("Coming Soon...")


ROUTES = {
    "dashboard": {
        "title": "",
        "view": dashboard_page,
        "admin_only": False,
    },

    "notifications": {
        "title": "Notifications",
        "view": notifications_page,
        "admin_only": False,
    },

    # Shift Management
    "shift_checklist": {
        "title": "Shift Management Checklist",
        #"message": "Opening, closing, prove-it and cleaning completion checklist for current shift.",
        "view": checklist_page,
        "admin_only": False,
    },
    "shift_diary": {
        "title": "Shift Diary",
        "view": shift_diary_page,
        "admin_only": False,
    },
    "shift_archive": {
        "title": "Shift Session Archive",
        "view": shift_archive_page,
        "admin_only": False,
    },

    "training_food_safety_take_quiz": {
        "title": "Take a Food Safety Quiz",
        "message": None,
        "admin_only": False,
    },
    "training_food_safety_create_quiz": {
        "title": "Create a Food Safety Quiz",
        "message": "AI-assisted food safety management quizzes builder and assignment of quizzes to staff members.",
        "admin_only": True,
    },
    "training_other": {
        "title": "Other Training",
        "message": None,
        "admin_only": False,
    },
    "training_staff_records": {
        "title": "Staff Training Records",
        "message": None,
        "admin_only": True,
    },

    # Food Safety
    "food_safety_qa": {
        "title": "Food Safety Q&A",
        "message": "AI-Assisted Food Safety Q&A chatbot.",
        "admin_only": False,
    },
    "food_safety_allergens_matrix": {
        "title": "Allergens Matrix",
        "message": "Includes filters by product, allergen and dish.",
        "admin_only": False,
    },
    "food_safety_edit_allergens_matrix": {
        "title": "Edit Allergens Matrix",
        "message": None,
        "admin_only": True,
    },
    "food_safety_cleaning_schedule": {
        "title": "Cleaning Schedule",
        "message": (
            "Future view for the business cleaning schedule. This page will display "
            "the generated cleaning tasks, frequencies, responsible roles, methods, "
            "records, and evidence needed for day-to-day food safety checks."
        ),
        "admin_only": False,
    },
    "food_safety_cleaning_schedule_builder": {
        "title": "Cleaning Schedule Builder",
        "message": (
            "Future builder for creating a bespoke cleaning schedule. This page will "
            "guide an admin user through setting up areas, cleaning methods, products, "
            "frequencies, responsibilities, and verification records."
        ),
        "admin_only": True,
    },

    # Procurement
    "procurement_suppliers_list": {
        "title": "Suppliers List",
        "message": None,
        "admin_only": False,
    },
    "procurement_invoices": {
        "title": "Invoices",
        "message": None,
        "admin_only": True,
    },
    "procurement_recalls_log": {
        "title": "Suppliers' Product Recalls Log",
        "message": None,
        "admin_only": True,
    },
    "procurement_maintenance": {
        "title": "Maintenance",
        "message": "Repairs and maintenance logs.",
        "admin_only": False,
    },

    # Compliance
    "compliance_food_safety_profile": {
        "title": "Food Safety Profile",
        "view": screening_page,
        "admin_only": True,
    },
    "compliance_food_safety_fsms_builder": {
        "title": "Food Safety Management System Builder",
        "view": approval_page,
        "admin_only": True,
    },
    "compliance_food_safety_approved_methods": {
        "title": "Approved Food Safety Methods",
        "view": approved_methods_page,
        "admin_only": False,
    },
    "compliance_food_safety_review": {
        "title": "Food Safety Management System Review",
        "message": "AI-assisted chatbot to introduce changes to the FSMS.",
        "admin_only": True,
    },
    "compliance_food_safety_chilling_equipment": {
        "title": "Chilling Equipment",
        "view": chilling_equipment_page.show,
        "admin_only": True,
    },
    "compliance_food_safety_processing_equipment": {
        "title": "Processing Equipment",
        "message": (
            "Future functionality will support food-processing equipment with "
            "implications for the Food Safety Management System, including "
            "cooling-down equipment, sous-vide equipment, hot-holding equipment, "
            "vacuum-packing equipment, meat slicers and meat grinders."
        ),
        "admin_only": True,
    },
    "compliance_health_safety": {
        "title": "Health & Safety Compliance",
        "message": None,
        "admin_only": True,
    },
    "compliance_fire_safety": {
        "title": "Fire Safety Compliance",
        "message": None,
        "admin_only": True,
    },
    "compliance_environmental_waste": {
        "title": "Environmental & Waste Compliance",
        "message": None,
        "admin_only": True,
    },
    "compliance_alcohol_licensing": {
        "title": "Alcohol License",
        "message": None,
        "admin_only": True,
    },
    "compliance_music_license": {
        "title": "Music License",
        "message": None,
        "admin_only": True,
    },
    "compliance_equipment": {
        "title": "Equipment Compliance",
        "message": None,
        "admin_only": True,
    },
    "compliance_premises_licensing": {
        "title": "Premises Licensing",
        "message": None,
        "admin_only": True,
    },
    "compliance_hr": {
        "title": "HR Compliance",
        "message": None,
        "admin_only": True,
    },

    # Settings and Admin
    "settings": {
        "title": "Settings",
        "message": (
            "Appearance, security, password change, notification preferences, "
            "and user profile settings."
        ),
        "admin_only": False,
    },
    "admin_users": {
        "title": "Venue User Administration",
        "view": admin_page,
        "admin_only": True,
    },
}


MENU_LABEL_TO_ROUTE = {
    "Dashboard": "dashboard",
    "Notifications": "notifications",

    "Checklist": "shift_checklist",
    "Diary": "shift_diary",
    "Archive": "shift_archive",

    "Take a Quiz": "training_food_safety_take_quiz",
    "Create a Quiz": "training_food_safety_create_quiz",
    "Other Training": "training_other",
    "Staff Training Records": "training_staff_records",

    "Q&A": "food_safety_qa",
    "Allergens Matrix": "food_safety_allergens_matrix",
    "Edit Allergens Matrix": "food_safety_edit_allergens_matrix",
    "Cleaning Schedule": "food_safety_cleaning_schedule",
    "Cleaning Schedule Builder": "food_safety_cleaning_schedule_builder",

    "Suppliers List": "procurement_suppliers_list",
    "Invoices": "procurement_invoices",
    "Recalls Log": "procurement_recalls_log",
    "Maintenance": "procurement_maintenance",

    "Profile Builder": "compliance_food_safety_profile",
    "FSMS Builder": "compliance_food_safety_fsms_builder",
    "Approved Methods": "compliance_food_safety_approved_methods",
    "FSMS Review": "compliance_food_safety_review",
    "Chilling Equipment": "compliance_food_safety_chilling_equipment",
    "Processing Equipment": "compliance_food_safety_processing_equipment",
    "Health & Safety": "compliance_health_safety",
    "Fire Safety": "compliance_fire_safety",
    "Environmental & Waste": "compliance_environmental_waste",
    "Alcohol Licensing": "compliance_alcohol_licensing",
    "Music License": "compliance_music_license",
    "Equipment Compliance": "compliance_equipment",
    "Premises Licensing": "compliance_premises_licensing",
    "HR Compliance": "compliance_hr",

    "Settings": "settings",
    "Users": "admin_users",
}


def get_navigation_items():
    training_children = [
        sac.MenuItem("Food Safety", children=[
            sac.MenuItem("Take a Quiz"),
        ]),
        sac.MenuItem("Other Training"),
    ]

    food_safety_children = [
        sac.MenuItem("Q&A"),
        sac.MenuItem("Approved Methods"),
        sac.MenuItem("Allergens Matrix"),
        sac.MenuItem("Cleaning Schedule"),
    ]

    procurement_children = [
        sac.MenuItem("Suppliers List"),
        sac.MenuItem("Maintenance"),
    ]


    unread_notification_count = load_unread_notification_count()
    notification_tag = [
        sac.Tag(str(unread_notification_count), color="red")
    ]

    menu_items = [
        sac.MenuItem("Dashboard", icon="house"),
        sac.MenuItem("Notifications", icon="bell", tag=notification_tag),
        sac.MenuItem("Shift Management", icon="calendar", children=[
            sac.MenuItem("Checklist"),
            sac.MenuItem("Diary"),
            sac.MenuItem("Archive"),
        ]),
    ]

    if is_admin():
        training_children[0].children.append(sac.MenuItem("Create a Quiz"))
        training_children.append(sac.MenuItem("Staff Training Records"))


        procurement_children.insert(1, sac.MenuItem("Invoices"))
        procurement_children.insert(2, sac.MenuItem("Recalls Log"))

    menu_items.extend([
        sac.MenuItem("Training", icon="book", children=training_children),
        sac.MenuItem("Food Safety", icon="shield-check", children=food_safety_children),
        sac.MenuItem("Procurement", icon="cart", children=procurement_children),
    ])

    if is_admin():
        menu_items.append(
            sac.MenuItem("Compliance", icon="check-circle", children=[
                sac.MenuItem("Food Safety", children=[
                    sac.MenuItem("Profile Builder"),
                    sac.MenuItem("FSMS Builder"),
                    sac.MenuItem("FSMS Review"),
                    sac.MenuItem("Critical Equipment", children=[
                        sac.MenuItem("Chilling Equipment"),
                        sac.MenuItem("Processing Equipment"),
                    ]),
                    sac.MenuItem("Cleaning Schedule Builder"),
                    sac.MenuItem("Edit Allergens Matrix"),
                ]),
                sac.MenuItem("Health & Safety"),
                sac.MenuItem("Fire Safety"),
                sac.MenuItem("Environmental & Waste"),
                sac.MenuItem("Alcohol Licensing"),
                sac.MenuItem("Music License"),
                sac.MenuItem("Equipment Compliance"),
                sac.MenuItem("Premises Licensing"),
                sac.MenuItem("HR Compliance"),
            ])
        )

    menu_items.append(sac.MenuItem("Settings", icon="gear"))

    if is_admin():
        menu_items.append(
            sac.MenuItem("Admin", icon="person-gear", children=[
                sac.MenuItem("Users"),
            ])
        )

    menu_items.append(sac.MenuItem("Logout", icon="box-arrow-right"))

    return menu_items


def load_sidebar_daily_shift_state():
    token = st.session_state.get("token")

    if not token:
        return None

    response = api_request(
        "GET",
        "/daily-shifts/current",
        token=token,
    )

    if response is None or response.status_code != 200:
        return None

    return response.json()


def format_shift_date(value):
    if not value:
        return "unknown date"

    try:
        year, month, day = value.split("-")
        return f"{day}-{month}-{year}"
    except ValueError:
        return value


def load_unread_notification_count():
    token = st.session_state.get("token")

    if not token:
        return 0

    response = api_request(
        "GET",
        "/notifications/unread-count",
        token=token,
    )

    if response is None or response.status_code != 200:
        return 0

    data = response.json()
    return data.get("unread_count", 0) or 0


def render_sidebar_shift_status():
    shift_state = load_sidebar_daily_shift_state()

    if not shift_state:
        return

    state = shift_state.get("state")
    shift = shift_state.get("shift") or {}

    if state == "active":
        st.sidebar.info(
            f"Active shift: {format_shift_date(shift.get('shift_date'))}\n\n"
            f"Started by: {shift.get('started_by_name') or 'Unknown user'}"
        )
        return

    if state == "ended":
        st.sidebar.info(
            f"Last ended shift: {format_shift_date(shift.get('shift_date'))}\n\n"
            f"Ended by: {shift.get('ended_by_name') or 'Unknown user'}"
        )


def render_sidebar():

    render_sidebar_shift_status()

    user = st.session_state.user or {}
    display_name = user.get("first_name") or user.get("email", "User")

    st.sidebar.write(f"Logged in as: {display_name}")

    business_name = user.get("business_name")
    site_name = user.get("site_name")

    if business_name:
        st.sidebar.write(f"Business: {business_name}")

    if site_name:
        st.sidebar.write(f"Venue: {site_name}")

    pending_navigation_route = st.session_state.pop(
        "pending_navigation_route",
        None,
    )

    pending_navigation_label = st.session_state.pop(
        "pending_navigation_label",
        None,
    )

    if pending_navigation_route:
        st.session_state.page = pending_navigation_route

    if pending_navigation_label:
        st.session_state.main_navigation = pending_navigation_label


    with st.sidebar:
        selected_label = sac.menu(
            items=get_navigation_items(),
            open_all=False,
            key="main_navigation",
        )

    if selected_label == "Logout":
        logout()

    selected_route = MENU_LABEL_TO_ROUTE.get(selected_label)

    if selected_route:
        st.session_state.page = selected_route

def clear_dashboard_shift_messages():
    dashboard_shift_state_keys = (
        "show_end_shift_confirmation",
        "end_shift_block_message",
        "daily_shift_end_notes",
    )

    for key in dashboard_shift_state_keys:
        st.session_state.pop(key, None)


def render_current_page():
    current_page = st.session_state.page

    if current_page != "notifications":
        st.session_state.pop("expanded_notification_id", None)

    if current_page != "shift_archive":
        st.session_state.pop("selected_archive_shift_id", None)
        st.session_state.pop("selected_archive_view", None)

    if current_page != "dashboard":
        clear_dashboard_shift_messages()

    if current_page not in ROUTES:
        st.session_state.page = "dashboard"
        dashboard_page()
        return

    route = ROUTES[current_page]

    if route.get("admin_only") and not is_admin():
        st.error("You do not have permission to access this page.")
        return

    view = route.get("view")

    if view:
        view()
        return

    show_placeholder(
        title=route["title"],
        message=route.get("message")
    )


# Routing.
if not st.session_state.authenticated:
    if st.session_state.page == "login":
        login_page()
    elif st.session_state.page == "register":
        register_page()
    elif st.session_state.page == "forgot":
        forgot_page()
    elif st.session_state.page == "reset":
        reset_page()
    else:
        landing()
else:
    render_sidebar()
    render_current_page()
