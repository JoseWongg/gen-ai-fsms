import json
from pathlib import Path


STRUCTURE_PATH = Path(
    "data/fsms_policy_document_structure.json"
)
SOURCE_CONTENT_PATH = Path(
    "data/sfbb_chilling_cooking.json"
)

EXPECTED_SECTIONS = [
    (
        "food_safety_policy",
        "1",
        "Food Safety Policy",
    ),
    (
        "business_scope_and_food_safety_overview",
        "2",
        "Business Scope and Food Safety Overview",
    ),
    (
        "chilling_and_temperature_control",
        "3",
        "Chilling and Temperature Control",
    ),
    (
        "cooking_and_reheating",
        "4",
        "Cooking and Reheating",
    ),
    (
        "cross_contamination_control",
        "5",
        "Cross-Contamination Control",
    ),
    (
        "cleaning_and_disinfection",
        "6",
        "Cleaning and Disinfection",
    ),
    (
        "allergen_management",
        "7",
        "Allergen Management",
    ),
    (
        "pest_control",
        "8",
        "Pest Control",
    ),
    (
        "deliveries_and_traceability",
        "9",
        "Deliveries and Traceability",
    ),
    (
        "training_responsibilities_and_review",
        "10",
        "Training, Responsibilities and Review",
    ),
]

EXPECTED_SUBSECTIONS = {
    "food_safety_policy": [
        ("purpose_and_scope", "1.1"),
        ("food_safety_commitment", "1.2"),
        ("responsibilities", "1.3"),
        (
            "monitoring_corrective_action_review",
            "1.4",
        ),
    ],
    "business_scope_and_food_safety_overview": [
        ("business_and_food_operations", "2.1"),
        ("activities_covered_by_fsms", "2.2"),
        ("main_food_safety_hazards", "2.3"),
        ("control_approach", "2.4"),
    ],
    "chilling_and_temperature_control": [
        ("chilled_storage_and_display", "3.1"),
        ("cooling_hot_food", "3.2"),
        ("defrosting", "3.3"),
        ("freezing", "3.4"),
        ("temperature_monitoring", "3.5"),
        ("fridge_temperature_checklist", "3.6"),
    ],
    "cooking_and_reheating": [
        ("cooking_safely", "4.1"),
        (
            "foods_requiring_additional_care",
            "4.2",
        ),
        ("reheating", "4.3"),
        ("hot_holding", "4.4"),
        ("ready_to_eat_food", "4.5"),
        (
            "cooking_checks_and_corrective_action",
            "4.6",
        ),
    ],
    "cross_contamination_control": [],
    "cleaning_and_disinfection": [],
    "allergen_management": [],
    "pest_control": [],
    "deliveries_and_traceability": [],
    "training_responsibilities_and_review": [],
}

EXPECTED_OPERATIONAL_MAPPINGS = {
    "chilled_storage_and_display": ["4.1"],
    "cooling_hot_food": ["4.2"],
    "defrosting": ["4.3"],
    "freezing": ["4.4"],
    "temperature_monitoring": [
        "4.1",
        "4.2",
        "4.3",
        "4.4",
    ],
    "cooking_safely": ["5.1"],
    "foods_requiring_additional_care": [
        "5.2",
        "5.4",
    ],
    "reheating": ["5.3"],
    "hot_holding": ["5.5"],
    "ready_to_eat_food": ["5.6"],
    "cooking_checks_and_corrective_action": [
        "5.1",
        "5.2",
        "5.3",
        "5.4",
        "5.5",
        "5.6",
    ],
}

ALLOWED_ROLES = {
    "text": {
        "introduction",
        "business_context",
        "food_safety_importance",
        "policy",
        "responsibilities",
        "procedure",
        "monitoring",
        "corrective_action",
        "review",
    },
    "list": {
        "business_context",
        "food_safety_importance",
        "policy",
        "responsibilities",
        "procedure",
        "monitoring",
        "corrective_action",
        "review",
    },
    "table": {
        "equipment",
        "monitoring",
        "checklist",
        "responsibilities",
    },
}

FORBIDDEN_KEYS = {
    "planned_section_count",
    "supported_section_count",
    "implementation_status",
    "completion_rule",
    "display_order",
    "counts_towards_business_completion",
    "counts_towards_product_coverage",
    "summary_subsection",
    "safe_method_introductions",
    "appendices",
}


def load_json(path: Path) -> dict:
    return json.loads(
        path.read_text(encoding="utf-8")
    )


def iter_dicts(value):
    if isinstance(value, dict):
        yield value

        for nested_value in value.values():
            yield from iter_dicts(nested_value)

    elif isinstance(value, list):
        for item in value:
            yield from iter_dicts(item)


def source_safe_method_ids() -> set[str]:
    source = load_json(SOURCE_CONTENT_PATH)

    return {
        safe_method["safe_method_id"]
        for section in source["sections"]
        for safe_method in section["safe_methods"]
    }


def configured_content_blocks(structure):
    for section in structure["sections"]:
        for definition in section.get(
            "content_definitions",
            [],
        ):
            yield definition

        for subsection in section["subsections"]:
            for definition in subsection.get(
                "content_definitions",
                [],
            ):
                yield definition

            for definition in subsection.get(
                "content_pattern",
                [],
            ):
                yield definition


def test_structure_has_policy_document_metadata():
    structure = load_json(STRUCTURE_PATH)

    assert structure["schema_version"] == "2.0"
    assert structure["document_title"] == (
        "Food Safety Management System"
    )
    assert structure["draft_notice"] == (
        "This document is incomplete and must not be "
        "treated as the final approved Food Safety "
        "Management System."
    )


def test_structure_contains_only_agreed_sections():
    sections = load_json(STRUCTURE_PATH)["sections"]

    actual = [
        (
            section["section_id"],
            section["section_number"],
            section["title"],
        )
        for section in sections
    ]

    assert actual == EXPECTED_SECTIONS


def test_structure_contains_agreed_subsections():
    sections = load_json(STRUCTURE_PATH)["sections"]

    for section in sections:
        actual = [
            (
                subsection["subsection_id"],
                subsection["subsection_number"],
            )
            for subsection in section["subsections"]
        ]

        assert actual == EXPECTED_SUBSECTIONS[
            section["section_id"]
        ]


def test_operational_source_mappings_are_controlled():
    sections = load_json(STRUCTURE_PATH)["sections"]

    actual = {
        subsection["subsection_id"]:
            subsection["source_safe_method_ids"]
        for section in sections
        for subsection in section["subsections"]
        if "source_safe_method_ids" in subsection
    }

    assert actual == EXPECTED_OPERATIONAL_MAPPINGS

    assert actual[
        "foods_requiring_additional_care"
    ] == ["5.2", "5.4"]


def test_configured_safe_methods_exist_in_source_data():
    structure = load_json(STRUCTURE_PATH)
    known_ids = source_safe_method_ids()

    configured_ids = {
        safe_method_id
        for section in structure["sections"]
        for subsection in section["subsections"]
        for safe_method_id in subsection.get(
            "source_safe_method_ids",
            [],
        )
    }

    assert configured_ids == known_ids


def test_content_definitions_match_policy_schema_roles():
    structure = load_json(STRUCTURE_PATH)

    for definition in configured_content_blocks(
        structure
    ):
        block_type = definition["block_type"]
        role = definition["role"]

        assert block_type in ALLOWED_ROLES
        assert role in ALLOWED_ROLES[block_type]


def test_structure_excludes_workflow_presentation():
    structure = load_json(STRUCTURE_PATH)

    for configured_object in iter_dicts(structure):
        assert (
            FORBIDDEN_KEYS
            & set(configured_object)
            == set()
        )

    assert "appendices" not in structure
    assert len(structure["sections"]) == 10


def test_business_personalisation_sources_are_controlled():
    structure = load_json(STRUCTURE_PATH)

    definitions = {
        definition["content_key"]: definition
        for section in structure["sections"]
        for definition in section.get(
            "content_definitions",
            [],
        )
    }

    assert definitions[
        "chilling_overall_policy"
    ]["dynamic_sources"] == [
        "business_name",
        "site_name",
    ]
    assert definitions[
        "cooking_overall_policy"
    ]["dynamic_sources"] == [
        "business_name",
        "site_name",
    ]

def test_beyond_scope_sections_use_controlled_notice():
    structure = load_json(STRUCTURE_PATH)
    sections = structure["sections"][4:]

    assert [
        section["section_number"]
        for section in sections
    ] == [
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
    ]

    for section in sections:
        assert (
            section["inclusion"]
            == "beyond_current_project_scope"
        )
        assert section["subsections"] == []
        assert section["content_definitions"] == [
            {
                "content_key": (
                    "beyond_current_project_scope"
                ),
                "block_type": "text",
                "role": "introduction",
                "heading": (
                    "Beyond current project scope"
                ),
                "text": (
                    "This section is included to show "
                    "the planned structure of the "
                    "complete Food Safety Management "
                    "System. Operational content for "
                    "this section is not currently "
                    "generated by the application."
                ),
            }
        ]

def test_named_responsibilities_content_is_controlled():
    structure = load_json(STRUCTURE_PATH)

    policy_section = next(
        section
        for section in structure["sections"]
        if section["section_id"]
        == "food_safety_policy"
    )
    responsibilities = next(
        subsection
        for subsection in policy_section["subsections"]
        if subsection["subsection_id"]
        == "responsibilities"
    )

    definitions = responsibilities[
        "content_definitions"
    ]

    assert [
        definition["content_key"]
        for definition in definitions
    ] == [
        "responsibilities_introduction",
        "responsibilities_list",
        "named_responsibilities_table",
    ]

    assert definitions[1]["items"][0] == (
        "The FSMS Responsible Person must maintain this "
        "FSMS, provide suitable resources, ensure staff "
        "are trained and supervised, and review the "
        "system when operations or risks change."
    )

    assert definitions[2] == {
        "content_key": "named_responsibilities_table",
        "block_type": "table",
        "role": "responsibilities",
        "dynamic_sources": [
            "fsms_responsible_person_name",
        ],
        "headers": [
            "Role",
            "Named person",
            "Main responsibility",
        ],
        "rows": [
            [
                "FSMS Responsible Person",
                "{fsms_responsible_person_name}",
                (
                    "Maintain the FSMS, provide suitable "
                    "resources, ensure staff are trained "
                    "and supervised, and review the "
                    "system when operations or risks "
                    "change."
                ),
            ],
        ],
        "source_references": [
            (
                "business_profile."
                "fsms_responsible_person_name"
            ),
        ],
    }
