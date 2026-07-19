from typing import Any, Dict

from gen_ai_fsms.schemas.fsms_document import FSMSDocumentArrangement


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
