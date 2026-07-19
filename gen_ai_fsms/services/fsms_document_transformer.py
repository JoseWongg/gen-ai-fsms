from typing import Any, Dict, List, Optional

from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocumentArrangement,
    FSMSDocumentRule,
    FSMSDocumentSection,
    FSMSDocumentSubsection,
)


CHILLING_EQUIPMENT_QUESTION_KEY = (
    "chilling_equipment_temperature_checks"
)

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
                _table_value(equipment.get("equipment_type")),
                _table_value(equipment.get("equipment_use")),
                _table_value(
                    equipment.get("temperature_check_method")
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
