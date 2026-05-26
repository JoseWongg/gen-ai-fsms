import streamlit as st
import streamlit_antd_components as sac

from views.login import show as login_page
from views.register import show as register_page
from views.dashboard import show as dashboard_page
from views.admin import show as admin_page
from views.forgot import show as forgot_page
from views.reset_password import show as reset_page
from views.onboarding_screening import show as screening_page


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
        "title": "Dashboard",
        "view": dashboard_page,
        "admin_only": False,
    },

    # Shift Management
    "shift_checklist": {
        "title": "Shift Management Checklist",
        "message": "Opening, closing, prove-it and cleaning completion checklist for current shift.",
        "admin_only": False,
    },
    "shift_diary": {
        "title": "Shift Diary",
        "message": (
            "Diary for current shift. Includes an AI chatbot that suggests and records entries "
            "in the diary and, alternatively, other logs such as the repairs log or recall log "
            "when appropriate. The AI layer can recognise recordable incidents and label incidents "
            "by type to support search functionality and can suggest corrective measures."
        ),
        "admin_only": False,
    },
    "shift_archive": {
        "title": "Diary Archive",
        "message": (
            "Repository of daily checklists and diary pages. Includes filter functionality "
            "and AI-assisted search across the records."
        ),
        "admin_only": False,
    },

    # Training
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
        "message": "Full view of the cleaning schedule.",
        "admin_only": False,
    },
    "food_safety_cleaning_schedule_builder": {
        "title": "Cleaning Schedule Builder",
        "message": (
            "AI-assisted chatbot to define equipment, restaurant layout, cleaning methods, "
            "scheduling and design a bespoke cleaning schedule accordingly."
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
        "message": "AI-Assisted chatbot to approve relevant food safety methods.",
        "admin_only": True,
    },
    "compliance_food_safety_approved_methods": {
        "title": "Approved Food Safety Methods",
        "message": None,
        "admin_only": True,
    },
    "compliance_food_safety_review": {
        "title": "Food Safety Management System Review",
        "message": "AI-assisted chatbot to introduce changes to the FSMS.",
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
    "admin": {
        "title": "Admin",
        "view": admin_page,
        "admin_only": True,
    },
}


MENU_LABEL_TO_ROUTE = {
    "Dashboard": "dashboard",

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

    "Profile": "compliance_food_safety_profile",
    "FSMS Builder": "compliance_food_safety_fsms_builder",
    "Approved Methods": "compliance_food_safety_approved_methods",
    "FSMS Review": "compliance_food_safety_review",
    "Health & Safety": "compliance_health_safety",
    "Fire Safety": "compliance_fire_safety",
    "Environmental & Waste": "compliance_environmental_waste",
    "Alcohol Licensing": "compliance_alcohol_licensing",
    "Music License": "compliance_music_license",
    "Equipment Compliance": "compliance_equipment",
    "Premises Licensing": "compliance_premises_licensing",
    "HR Compliance": "compliance_hr",

    "Settings": "settings",
    "Admin": "admin",
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
        sac.MenuItem("Allergens", children=[
            sac.MenuItem("Allergens Matrix"),
        ]),
        sac.MenuItem("Cleaning", children=[
            sac.MenuItem("Cleaning Schedule"),
        ]),
    ]

    procurement_children = [
        sac.MenuItem("Suppliers List"),
        sac.MenuItem("Maintenance"),
    ]

    menu_items = [
        sac.MenuItem("Dashboard", icon="house"),
        sac.MenuItem("Shift Management", icon="calendar", children=[
            sac.MenuItem("Checklist"),
            sac.MenuItem("Diary"),
            sac.MenuItem("Archive"),
        ]),
    ]

    if is_admin():
        training_children[0].children.append(sac.MenuItem("Create a Quiz"))
        training_children.append(sac.MenuItem("Staff Training Records"))

        food_safety_children[1].children.append(sac.MenuItem("Edit Allergens Matrix"))
        food_safety_children[2].children.append(sac.MenuItem("Cleaning Schedule Builder"))

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
                    sac.MenuItem("Profile"),
                    sac.MenuItem("FSMS Builder"),
                    sac.MenuItem("Approved Methods"),
                    sac.MenuItem("FSMS Review"),
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
        menu_items.append(sac.MenuItem("Admin", icon="person-gear"))

    menu_items.append(sac.MenuItem("Logout", icon="box-arrow-right"))

    return menu_items


def render_sidebar():
    st.sidebar.title("Navigation")

    user = st.session_state.user or {}
    display_name = user.get("first_name", user.get("email", "User"))
    st.sidebar.write(f"Logged in as: {display_name}")

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


def render_current_page():
    current_page = st.session_state.page

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