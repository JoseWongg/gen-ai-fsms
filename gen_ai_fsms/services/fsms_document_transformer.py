from datetime import datetime
from typing import Any, Dict, List, Optional

from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocument,
    FSMSDocumentAppendix,
    FSMSDocumentArrangement,
    FSMSDocumentProgress,
    FSMSDocumentRule,
    FSMSDocumentSection,
    FSMSDocumentSubsection,
)


CHILLING_EQUIPMENT_QUESTION_KEY = (
    "chilling_equipment_temperature_checks"
)

CHILLING_EQUIPMENT_VALUE_LABELS = {
    "equipment_type": {
        "fridge": "Fridge",
        "freezer": "Freezer",
    },
    "equipment_use": {
        "storage": "Storage",
        "display": "Display",
    },
    "temperature_check_method": {
        "digital_or_dial_display": "Digital/dial display",
        "probe_between_packs": "Probe between packs",
    },
}


ADDITIONAL_RESPONSE_TITLES = {
    CHILLING_EQUIPMENT_QUESTION_KEY: (
        "Chilling equipment and temperature checks"
    ),
    "foods_defrosted_under_cold_running_water": (
        "Foods defrosted under cold running water"
    ),
    "foods_defrosted_in_microwave": (
        "Foods defrosted in a microwave"
    ),
    "foods_defrosted_at_room_temperature": (
        "Foods defrosted at room temperature"
    ),
    "foods_defrosted_in_sink": (
        "Foods defrosted in a sink"
    ),
    "dishes_containing_cooked_whole_birds": (
        "Dishes containing cooked whole birds"
    ),
    "liquid_dishes": "Liquid dishes",
    "dishes_containing_rare_beef_or_lamb": (
        "Dishes containing rare beef or lamb"
    ),
    "dishes_containing_pork": "Dishes containing pork",
    "dishes_containing_rolled_joints_of_meat": (
        "Dishes containing rolled joints of meat"
    ),
    "dishes_containing_processed_meat_products": (
        "Dishes containing processed meat products"
    ),
    "dishes_containing_offal": "Dishes containing offal",
    "curries_stews_with_large_pieces_of_meat": (
        "Curries and stews with large pieces of meat"
    ),
    "combination_dishes": "Combination dishes",
    "dishes_containing_cooked_fish": (
        "Dishes containing cooked fish"
    ),
    "dishes_containing_rare_fish": (
        "Dishes containing rare fish"
    ),
    "dishes_containing_eggs": "Dishes containing eggs",
    "dishes_containing_crustaceans": (
        "Dishes containing crustaceans"
    ),
    "dishes_containing_molluscs": (
        "Dishes containing molluscs"
    ),
    "hot_holding_equipment": "Hot-holding equipment",
}


def transform_additional_response(
    *,
    safety_point_id: str,
    response: Dict[str, Any],
) -> FSMSDocumentArrangement:
    """
    Convert one stored additional response into document content.

    This function performs no database access and no LLM calls.
    """
    question_key = response.get("question_key")

    if question_key not in ADDITIONAL_RESPONSE_TITLES:
        raise ValueError(
            "Unsupported FSMS document question key: "
            f"'{question_key}'."
        )

    if question_key == CHILLING_EQUIPMENT_QUESTION_KEY:
        return _transform_chilling_equipment_response(
            safety_point_id=safety_point_id,
            response=response,
        )

    document_response_text = response.get(
        "document_response_text"
    )

    if (
        not isinstance(document_response_text, str)
        or not document_response_text.strip()
    ):
        raise ValueError(
            "Missing document response text for additional question "
            f"'{question_key}'."
        )

    return FSMSDocumentArrangement(
        arrangement_type="additional_question_response",
        title=ADDITIONAL_RESPONSE_TITLES[question_key],
        statements=[document_response_text.strip()],
        source_safety_point_id=safety_point_id,
        source_question_key=question_key,
    )


def _transform_chilling_equipment_response(
    *,
    safety_point_id: str,
    response: Dict[str, Any],
) -> FSMSDocumentArrangement:
    equipment_items = response.get("current_chilling_equipment")

    if not isinstance(equipment_items, list):
        raise ValueError(
            "Missing current chilling equipment for FSMS document."
        )

    if not equipment_items:
        return FSMSDocumentArrangement(
            arrangement_type="chilling_equipment_table",
            title=ADDITIONAL_RESPONSE_TITLES[
                CHILLING_EQUIPMENT_QUESTION_KEY
            ],
            statements=[
                "No active chilling equipment is currently recorded."
            ],
            source_safety_point_id=safety_point_id,
            source_question_key=CHILLING_EQUIPMENT_QUESTION_KEY,
        )

    table_rows = []

    for equipment in equipment_items:
        if not isinstance(equipment, dict):
            raise ValueError(
                "Invalid chilling equipment record for FSMS document."
            )

        table_rows.append(
            [
                _table_value(equipment.get("equipment_asset_code")),
                _table_value(equipment.get("equipment_name")),
                _format_chilling_equipment_value(
                    "equipment_type",
                    equipment.get("equipment_type"),
                ),
                _format_chilling_equipment_value(
                    "equipment_use",
                    equipment.get("equipment_use"),
                ),
                _format_chilling_equipment_value(
                    "temperature_check_method",
                    equipment.get("temperature_check_method"),
                ),
            ]
        )

    return FSMSDocumentArrangement(
        arrangement_type="chilling_equipment_table",
        title=ADDITIONAL_RESPONSE_TITLES[
            CHILLING_EQUIPMENT_QUESTION_KEY
        ],
        table_headers=[
            "Asset code",
            "Equipment",
            "Type",
            "Use",
            "Temperature check method",
        ],
        table_rows=table_rows,
        source_safety_point_id=safety_point_id,
        source_question_key=CHILLING_EQUIPMENT_QUESTION_KEY,
    )


def _table_value(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()



def _format_chilling_equipment_value(
    field_name: str,
    value: Any,
) -> str:
    cleaned_value = _table_value(value)

    if not cleaned_value:
        return ""

    configured_labels = CHILLING_EQUIPMENT_VALUE_LABELS.get(
        field_name,
        {},
    )

    configured_label = configured_labels.get(cleaned_value)

    if configured_label is not None:
        return configured_label

    return (
        cleaned_value.replace("_", " ")
        .replace("-", " ")
        .capitalize()
    )


def build_supported_control_section(
    *,
    section_config: Dict[str, Any],
    safe_method_introductions: Dict[str, Dict[str, str]],
    applicable_safety_points: List[Dict[str, Any]],
    approved_safety_points: List[Dict[str, Any]],
) -> Optional[FSMSDocumentSection]:
    """
    Build one supported operational FSMS section.

    The function receives already-loaded data. It performs no database access
    and no LLM calls. A non-applicable section is omitted by returning None.
    """
    if section_config.get("implementation_status") != "supported":
        raise ValueError(
            "Only supported FSMS document sections can be built by "
            "build_supported_control_section."
        )

    source_section_ids = set(
        section_config.get("source_section_ids", [])
    )

    if not source_section_ids:
        raise ValueError(
            "A supported control section must define source section IDs."
        )

    section_safety_points = [
        safety_point
        for safety_point in applicable_safety_points
        if safety_point.get("section_id") in source_section_ids
    ]

    if not section_safety_points:
        return None

    approved_by_safety_point_id: Dict[str, Dict[str, Any]] = {}

    for approved_safety_point in approved_safety_points:
        safety_point_id = approved_safety_point.get(
            "safety_point_id"
        )

        if not safety_point_id:
            continue

        if safety_point_id in approved_by_safety_point_id:
            raise ValueError(
                "Duplicate approved safety point supplied for FSMS "
                f"document: '{safety_point_id}'."
            )

        approved_by_safety_point_id[safety_point_id] = (
            approved_safety_point
        )

    safety_points_by_safe_method: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    for safety_point in section_safety_points:
        safe_method_id = safety_point.get("safe_method_id")

        if not safe_method_id:
            raise ValueError(
                "Applicable safety point is missing a safe method ID."
            )

        safety_points_by_safe_method.setdefault(
            safe_method_id,
            [],
        ).append(safety_point)

    configured_safe_method_ids = [
        safe_method_id
        for safe_method_id, safe_method_config
        in safe_method_introductions.items()
        if safe_method_config.get("source_section_id")
        in source_section_ids
    ]

    unknown_safe_method_ids = (
        set(safety_points_by_safe_method)
        - set(configured_safe_method_ids)
    )

    if unknown_safe_method_ids:
        unknown_value = sorted(unknown_safe_method_ids)[0]
        raise ValueError(
            "Missing FSMS document safe-method configuration for "
            f"'{unknown_value}'."
        )

    subsections = []

    for safe_method_id in configured_safe_method_ids:
        method_safety_points = safety_points_by_safe_method.get(
            safe_method_id,
            [],
        )

        if not method_safety_points:
            continue

        safe_method_config = safe_method_introductions[
            safe_method_id
        ]

        approved_rules = []
        arrangements = []
        subsection_references = []
        approved_method_count = 0

        for safety_point in method_safety_points:
            safety_point_id = safety_point.get("safety_point_id")
            approved_safety_point = (
                approved_by_safety_point_id.get(safety_point_id)
            )

            if approved_safety_point is None:
                continue

            approved_method_count += 1

            instruction = safety_point.get("instruction")

            if not isinstance(instruction, str) or not instruction.strip():
                raise ValueError(
                    "Approved safety point is missing its document "
                    f"instruction: '{safety_point_id}'."
                )

            rule_references = _collect_references(
                safety_point.get("source_references", []),
                safety_point.get(
                    "additional_source_references",
                    [],
                ),
                approved_safety_point.get(
                    "provenance_references",
                    [],
                ),
            )

            approved_rules.append(
                FSMSDocumentRule(
                    safety_point_id=safety_point_id,
                    instruction=instruction.strip(),
                    source_references=rule_references,
                )
            )

            subsection_references = _collect_references(
                subsection_references,
                rule_references,
            )

            for response in approved_safety_point.get(
                "additional_responses",
                [],
            ):
                arrangements.append(
                    transform_additional_response(
                        safety_point_id=safety_point_id,
                        response=response,
                    )
                )

        method_status = (
            "completed"
            if approved_method_count == len(method_safety_points)
            else "not_completed"
        )

        subsections.append(
            FSMSDocumentSubsection(
                safe_method_id=safe_method_id,
                title=safe_method_config["title"],
                introduction=safe_method_config["introduction"],
                status=method_status,
                approved_rules=approved_rules,
                business_specific_arrangements=arrangements,
                source_references=subsection_references,
            )
        )

    applicable_count = len(section_safety_points)
    approved_count = sum(
        1
        for safety_point in section_safety_points
        if safety_point.get("safety_point_id")
        in approved_by_safety_point_id
    )
    outstanding_count = applicable_count - approved_count
    section_status = (
        "completed"
        if outstanding_count == 0
        else "not_completed"
    )

    completion_message = None

    if outstanding_count:
        noun = (
            "safety point"
            if outstanding_count == 1
            else "safety points"
        )
        verb = "requires" if outstanding_count == 1 else "require"

        completion_message = (
            f"Not completed: {outstanding_count} applicable "
            f"{noun} still {verb} approval."
        )

    return FSMSDocumentSection(
        section_id=section_config["section_id"],
        title=section_config["title"],
        display_order=section_config["display_order"],
        status=section_status,
        introduction=section_config["introduction"],
        completion_message=completion_message,
        applicable_safety_point_count=applicable_count,
        approved_safety_point_count=approved_count,
        outstanding_safety_point_count=outstanding_count,
        subsections=subsections,
    )


def _collect_references(
    *reference_groups: List[str],
) -> List[str]:
    references = []

    for reference_group in reference_groups:
        for reference in reference_group or []:
            if reference and reference not in references:
                references.append(reference)

    return references



def build_beyond_scope_section(
    *,
    section_config: Dict[str, Any],
) -> FSMSDocumentSection:
    """
    Build a controlled placeholder for a planned unsupported section.
    """
    if (
        section_config.get("implementation_status")
        != "beyond_prototype_scope"
    ):
        raise ValueError(
            "Only beyond-prototype-scope sections can be built by "
            "build_beyond_scope_section."
        )

    return FSMSDocumentSection(
        section_id=section_config["section_id"],
        title=section_config["title"],
        display_order=section_config["display_order"],
        status="beyond_prototype_scope",
        introduction=section_config["introduction"],
        completion_message="Beyond prototype scope",
        applicable_safety_point_count=0,
        approved_safety_point_count=0,
        outstanding_safety_point_count=0,
        subsections=[],
    )


def build_document_progress(
    *,
    structure_config: Dict[str, Any],
    sections: List[FSMSDocumentSection],
) -> FSMSDocumentProgress:
    """
    Calculate completion and product-coverage values.

    Supported sections that are always applicable remain in the completion
    denominator even if their section content has not yet been built.
    Non-applicable operational sections are omitted from the denominator.
    Beyond-scope sections affect product coverage only.
    """
    configured_sections = structure_config.get("sections")

    if not isinstance(configured_sections, list):
        raise ValueError(
            "FSMS document structure must contain a section list."
        )

    configured_by_id: Dict[str, Dict[str, Any]] = {}

    for section_config in configured_sections:
        section_id = section_config.get("section_id")

        if not section_id:
            raise ValueError(
                "FSMS document section configuration is missing "
                "a section ID."
            )

        if section_id in configured_by_id:
            raise ValueError(
                "Duplicate FSMS document section configuration: "
                f"'{section_id}'."
            )

        configured_by_id[section_id] = section_config

    built_by_id: Dict[str, FSMSDocumentSection] = {}

    for section in sections:
        if section.section_id in built_by_id:
            raise ValueError(
                "Duplicate built FSMS document section: "
                f"'{section.section_id}'."
            )

        section_config = configured_by_id.get(section.section_id)

        if section_config is None:
            raise ValueError(
                "Built FSMS document section is not configured: "
                f"'{section.section_id}'."
            )

        implementation_status = section_config.get(
            "implementation_status"
        )

        if (
            implementation_status == "supported"
            and section.status == "beyond_prototype_scope"
        ):
            raise ValueError(
                "Supported FSMS document section cannot use the "
                "beyond-prototype-scope status."
            )

        if (
            implementation_status == "beyond_prototype_scope"
            and section.status != "beyond_prototype_scope"
        ):
            raise ValueError(
                "Beyond-prototype-scope section must use the "
                "matching section status."
            )

        built_by_id[section.section_id] = section

    applicable_supported_count = 0
    completed_applicable_count = 0

    for section_config in configured_sections:
        if section_config.get("implementation_status") != "supported":
            continue

        if (
            section_config.get(
                "counts_towards_business_completion"
            )
            is not True
        ):
            continue

        built_section = built_by_id.get(
            section_config["section_id"]
        )

        if built_section is None:
            if section_config.get("always_applicable") is True:
                applicable_supported_count += 1

            continue

        applicable_supported_count += 1

        if built_section.status == "completed":
            completed_applicable_count += 1

    if applicable_supported_count == 0:
        completion_percentage = 0
    else:
        completion_percentage = round(
            completed_applicable_count
            / applicable_supported_count
            * 100
        )

    if completed_applicable_count == 0:
        document_status = "not_started"
    elif (
        completed_applicable_count
        == applicable_supported_count
    ):
        document_status = "completed"
    else:
        document_status = "in_progress"

    supported_section_count = structure_config.get(
        "supported_section_count"
    )
    planned_section_count = structure_config.get(
        "planned_section_count"
    )

    if not isinstance(supported_section_count, int):
        raise ValueError(
            "FSMS document structure is missing the supported "
            "section count."
        )

    if not isinstance(planned_section_count, int):
        raise ValueError(
            "FSMS document structure is missing the planned "
            "section count."
        )

    return FSMSDocumentProgress(
        completed_applicable_section_count=(
            completed_applicable_count
        ),
        applicable_supported_section_count=(
            applicable_supported_count
        ),
        completion_percentage=completion_percentage,
        supported_section_count=supported_section_count,
        planned_section_count=planned_section_count,
        document_status=document_status,
        main_value=(
            f"{completed_applicable_count}/"
            f"{applicable_supported_count}"
        ),
        completion_caption=(
            "Applicable prototype sections completed"
        ),
        coverage_caption=(
            f"{supported_section_count} of "
            f"{planned_section_count} planned FSMS sections "
            "supported"
        ),
    )



def build_fsms_document(
    *,
    structure_config: Dict[str, Any],
    business_profile: Dict[str, Any],
    generated_at: datetime,
    supported_sections: List[FSMSDocumentSection],
) -> FSMSDocument:
    """
    Assemble the complete structured FSMS document.

    The caller supplies supported sections that have already been
    transformed. Missing always-applicable supported sections are shown as
    not completed. Missing operational sections are treated as
    non-applicable and omitted.
    """
    document_title = structure_config.get("document_title")

    if not isinstance(document_title, str) or not document_title.strip():
        raise ValueError(
            "FSMS document structure is missing the document title."
        )

    configured_sections = structure_config.get("sections")

    if not isinstance(configured_sections, list):
        raise ValueError(
            "FSMS document structure must contain a section list."
        )

    configured_by_id = {
        section_config.get("section_id"): section_config
        for section_config in configured_sections
        if section_config.get("section_id")
    }

    supplied_by_id: Dict[str, FSMSDocumentSection] = {}

    for section in supported_sections:
        if section.section_id in supplied_by_id:
            raise ValueError(
                "Duplicate supported FSMS document section supplied: "
                f"'{section.section_id}'."
            )

        section_config = configured_by_id.get(section.section_id)

        if section_config is None:
            raise ValueError(
                "Supplied FSMS document section is not configured: "
                f"'{section.section_id}'."
            )

        if section_config.get("implementation_status") != "supported":
            raise ValueError(
                "Only supported FSMS document sections may be "
                "supplied to build_fsms_document."
            )

        if (
            section.title != section_config.get("title")
            or section.display_order
            != section_config.get("display_order")
        ):
            raise ValueError(
                "Supplied FSMS document section does not match its "
                f"controlled structure: '{section.section_id}'."
            )

        supplied_by_id[section.section_id] = section

    document_sections = []

    for section_config in sorted(
        configured_sections,
        key=lambda item: item["display_order"],
    ):
        implementation_status = section_config.get(
            "implementation_status"
        )

        if implementation_status == "beyond_prototype_scope":
            document_sections.append(
                build_beyond_scope_section(
                    section_config=section_config,
                )
            )
            continue

        if implementation_status != "supported":
            raise ValueError(
                "Unsupported FSMS document implementation status: "
                f"'{implementation_status}'."
            )

        supplied_section = supplied_by_id.get(
            section_config["section_id"]
        )

        if supplied_section is not None:
            document_sections.append(supplied_section)
            continue

        if section_config.get("always_applicable") is True:
            document_sections.append(
                _build_incomplete_supported_section(
                    section_config=section_config,
                )
            )

    appendix_configs = structure_config.get("appendices")

    if not isinstance(appendix_configs, list):
        raise ValueError(
            "FSMS document structure must contain an appendix list."
        )

    appendices = [
        FSMSDocumentAppendix(
            appendix_id=appendix_config["appendix_id"],
            title=appendix_config["title"],
            display_order=appendix_config["display_order"],
        )
        for appendix_config in sorted(
            appendix_configs,
            key=lambda item: item["display_order"],
        )
    ]

    progress = build_document_progress(
        structure_config=structure_config,
        sections=document_sections,
    )

    return FSMSDocument(
        document_title=document_title.strip(),
        business_name=_required_profile_text(
            business_profile,
            "business_name",
        ),
        site_name=_required_profile_text(
            business_profile,
            "site_name",
        ),
        business_type=_optional_profile_text(
            business_profile,
            "business_type",
        ),
        business_description=_optional_profile_text(
            business_profile,
            "business_description",
        ),
        generated_at=generated_at,
        progress=progress,
        sections=document_sections,
        appendices=appendices,
    )


def _build_incomplete_supported_section(
    *,
    section_config: Dict[str, Any],
) -> FSMSDocumentSection:
    if (
        section_config.get("implementation_status") != "supported"
        or section_config.get("always_applicable") is not True
    ):
        raise ValueError(
            "Only always-applicable supported sections can use the "
            "incomplete placeholder."
        )

    return FSMSDocumentSection(
        section_id=section_config["section_id"],
        title=section_config["title"],
        display_order=section_config["display_order"],
        status="not_completed",
        introduction=section_config["introduction"],
        completion_message="Not completed",
    )


def _required_profile_text(
    business_profile: Dict[str, Any],
    field_name: str,
) -> str:
    value = business_profile.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "Business profile is missing required document field "
            f"'{field_name}'."
        )

    return value.strip()


def _optional_profile_text(
    business_profile: Dict[str, Any],
    field_name: str,
) -> Optional[str]:
    value = business_profile.get(field_name)

    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(
            "Business profile document field must be text: "
            f"'{field_name}'."
        )

    value = value.strip()

    return value or None
