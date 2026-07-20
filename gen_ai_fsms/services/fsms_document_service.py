import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocument,
    FSMSDocumentArrangement,
    FSMSDocumentSection,
    FSMSDocumentSubsection,
)
from gen_ai_fsms.services.fsms_document_transformer import (
    build_fsms_document,
    build_supported_control_section,
)
from gen_ai_fsms.services.safety_point_approval_service import (
    get_approved_methods_for_profile,
    get_condition_values_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
)
from gen_ai_fsms.services.screening_questions import (
    get_questions_for_condition_values,
)


FSMS_DOCUMENT_STRUCTURE_PATH = Path(
    "data/fsms_document_structure.json"
)

BUSINESS_TYPE_LABELS = {
    "restaurant": "Restaurant",
    "cafe": "Cafe",
    "bakery": "Bakery",
    "takeaway": "Takeaway",
    "sandwich_shop": "Sandwich shop",
    "pub_or_bar": "Pub or bar",
    "mobile_caterer": "Mobile caterer",
    "care_home_kitchen": "Care home kitchen",
    "school_or_college_kitchen": (
        "School or college kitchen"
    ),
    "hotel_or_guesthouse": "Hotel or guesthouse",
    "retail_food_shop": "Retail food shop",
    "other": "Other",
}


def load_fsms_document_structure(
    path: Path = FSMS_DOCUMENT_STRUCTURE_PATH,
) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"FSMS document structure file not found: {path}"
        )

    structure = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(structure, dict):
        raise ValueError(
            "FSMS document structure must contain a JSON object."
        )

    return structure


def generate_fsms_document_for_profile(
    *,
    db: Session,
    business_profile_id: int,
    generated_at: Optional[datetime] = None,
    structure_config: Optional[Dict[str, Any]] = None,
) -> FSMSDocument:
    """
    Generate the live structured FSMS document for one business profile.

    The document is rebuilt from current stored data. No document snapshot is
    persisted, and this function performs no database writes or LLM calls.
    """
    profile = (
        db.query(BusinessProfile)
        .filter(BusinessProfile.id == business_profile_id)
        .first()
    )

    if profile is None:
        raise ValueError(
            f"Business profile not found: {business_profile_id}."
        )

    structure = (
        structure_config
        if structure_config is not None
        else load_fsms_document_structure()
    )

    configured_sections = structure.get("sections")

    if not isinstance(configured_sections, list):
        raise ValueError(
            "FSMS document structure must contain a section list."
        )

    safe_method_introductions = structure.get(
        "safe_method_introductions"
    )

    if not isinstance(safe_method_introductions, dict):
        raise ValueError(
            "FSMS document structure must contain safe-method "
            "introductions."
        )

    screening_status = get_screening_completion_status(
        db=db,
        business_profile_id=business_profile_id,
    )
    condition_values = get_condition_values_for_profile(
        db=db,
        business_profile_id=business_profile_id,
    )
    business_profile_view = {
        "business_name": profile.business_name,
        "site_name": profile.site_name,
        "business_type": _format_business_type(
            profile.business_type
        ),
        "business_description": profile.business_description,
    }
    applicable_safety_points = (
        get_relevant_safety_points_for_profile(
            db=db,
            business_profile_id=business_profile_id,
        )
    )
    approved_methods = get_approved_methods_for_profile(
        db=db,
        business_profile_id=business_profile_id,
    )
    approved_safety_points = approved_methods.get(
        "approved_safety_points"
    )

    if not isinstance(applicable_safety_points, list):
        raise ValueError(
            "Applicable safety point data must be a list."
        )

    if not isinstance(approved_safety_points, list):
        raise ValueError(
            "Approved safety point data must be a list."
        )

    profile_complete = _is_business_profile_complete(profile)
    screening_complete = (
        screening_status.get("is_complete") is True
    )
    supported_sections = []

    for section_config in configured_sections:
        if (
            section_config.get("implementation_status")
            != "supported"
        ):
            continue

        source_section_ids = section_config.get(
            "source_section_ids",
            [],
        )

        if source_section_ids:
            control_section = build_supported_control_section(
                section_config=section_config,
                safe_method_introductions=(
                    safe_method_introductions
                ),
                applicable_safety_points=(
                    applicable_safety_points
                ),
                approved_safety_points=approved_safety_points,
            )

            if control_section is not None:
                supported_sections.append(control_section)

            continue

        supported_sections.append(
            _build_summary_section(
                section_config=section_config,
                business_profile=business_profile_view,
                condition_values=condition_values,
                profile_complete=profile_complete,
                screening_complete=screening_complete,
            )
        )


    return build_fsms_document(
        structure_config=structure,
        business_profile=business_profile_view,
        generated_at=(
            generated_at
            if generated_at is not None
            else datetime.now(timezone.utc)
        ),
        supported_sections=supported_sections,
    )


def _build_summary_section(
    *,
    section_config: Dict[str, Any],
    business_profile: Dict[str, Any],
    condition_values: Dict[str, str],
    profile_complete: bool,
    screening_complete: bool,
) -> FSMSDocumentSection:
    completion_rule = section_config.get("completion_rule")
    summary_config = section_config.get("summary_subsection")

    if not isinstance(summary_config, dict):
        raise ValueError(
            "FSMS summary section is missing controlled "
            f"content configuration: "
            f"'{section_config.get('section_id')}'."
        )

    if completion_rule == "business_profile_complete":
        is_complete = profile_complete
        incomplete_message = (
            "Not completed: business profile information is "
            "incomplete."
        )
        arrangements = [
            _build_policy_arrangement(
                summary_config=summary_config,
                business_profile=business_profile,
            )
        ]
    elif completion_rule == "food_safety_profile_complete":
        is_complete = profile_complete and screening_complete
        incomplete_message = (
            "Not completed: Food Safety Profile screening is "
            "incomplete."
        )
        arrangements = [
            _build_business_overview_arrangement(
                summary_config=summary_config,
                business_profile=business_profile,
            ),
            _build_screening_profile_arrangement(
                summary_config=summary_config,
                condition_values=condition_values,
            ),
        ]
    else:
        raise ValueError(
            "Unsupported FSMS document summary completion rule: "
            f"'{completion_rule}'."
        )

    status = (
        "completed"
        if is_complete
        else "not_completed"
    )

    subsection = FSMSDocumentSubsection(
        safe_method_id=_required_summary_config_text(
            summary_config,
            "subsection_id",
        ),
        title=_required_summary_config_text(
            summary_config,
            "title",
        ),
        introduction=_required_summary_config_text(
            summary_config,
            "introduction",
        ),
        status=status,
        business_specific_arrangements=arrangements,
    )

    return FSMSDocumentSection(
        section_id=section_config["section_id"],
        title=section_config["title"],
        display_order=section_config["display_order"],
        status=status,
        introduction=section_config["introduction"],
        completion_message=(
            None
            if is_complete
            else incomplete_message
        ),
        subsections=[subsection],
    )


def _build_policy_arrangement(
    *,
    summary_config: Dict[str, Any],
    business_profile: Dict[str, Any],
) -> FSMSDocumentArrangement:
    templates = summary_config.get("policy_statements")

    if (
        not isinstance(templates, list)
        or not templates
        or not all(
            isinstance(template, str) and template.strip()
            for template in templates
        )
    ):
        raise ValueError(
            "Food Safety Policy configuration must contain "
            "policy statements."
        )

    format_values = {
        "business_name": _required_business_profile_text(
            business_profile,
            "business_name",
        ),
        "site_name": _required_business_profile_text(
            business_profile,
            "site_name",
        ),
    }

    try:
        statements = [
            template.format(**format_values)
            for template in templates
        ]
    except KeyError as exc:
        raise ValueError(
            "Unsupported Food Safety Policy template value: "
            f"'{exc.args[0]}'."
        ) from exc

    return FSMSDocumentArrangement(
        arrangement_type="policy_statement",
        title=_required_summary_config_text(
            summary_config,
            "arrangement_title",
        ),
        statements=statements,
    )


def _build_business_overview_arrangement(
    *,
    summary_config: Dict[str, Any],
    business_profile: Dict[str, Any],
) -> FSMSDocumentArrangement:
    business_name = _required_business_profile_text(
        business_profile,
        "business_name",
    )
    site_name = _required_business_profile_text(
        business_profile,
        "site_name",
    )
    business_type = business_profile.get("business_type")
    business_description = business_profile.get(
        "business_description"
    )

    statements = [
        f"{site_name} is operated by {business_name}.",
    ]

    if isinstance(business_type, str) and business_type.strip():
        statements.append(
            "The recorded business type is "
            f"{business_type.strip()}."
        )
    else:
        statements.append(
            "The business type has not been recorded."
        )

    if (
        isinstance(business_description, str)
        and business_description.strip()
    ):
        statements.append(
            "Business description: "
            f"{business_description.strip()}"
        )
    else:
        statements.append(
            "A business description has not been recorded."
        )

    return FSMSDocumentArrangement(
        arrangement_type="business_overview",
        title=_required_summary_config_text(
            summary_config,
            "business_arrangement_title",
        ),
        statements=statements,
    )


def _build_screening_profile_arrangement(
    *,
    summary_config: Dict[str, Any],
    condition_values: Dict[str, str],
) -> FSMSDocumentArrangement:
    headers = summary_config.get(
        "screening_table_headers"
    )

    if (
        not isinstance(headers, list)
        or len(headers) != 2
        or not all(
            isinstance(header, str) and header.strip()
            for header in headers
        )
    ):
        raise ValueError(
            "Food Safety Profile configuration must contain "
            "two table headers."
        )

    return FSMSDocumentArrangement(
        arrangement_type="food_safety_profile_table",
        title=_required_summary_config_text(
            summary_config,
            "screening_arrangement_title",
        ),
        table_headers=[
            header.strip()
            for header in headers
        ],
        table_rows=_build_screening_profile_rows(
            condition_values
        ),
    )


def _build_screening_profile_rows(
    condition_values: Dict[str, str],
) -> list[list[str]]:
    answer_labels = {
        "true": "Yes",
        "false": "No",
    }
    rows = []

    for question in get_questions_for_condition_values(
        condition_values
    ):
        condition_ids = question.get(
            "sets_conditions",
            [],
        )

        if not condition_ids:
            continue

        recorded_value = condition_values.get(
            condition_ids[0]
        )

        rows.append(
            [
                question["text"],
                answer_labels.get(
                    recorded_value,
                    "Not recorded",
                ),
            ]
        )

    return rows


def _required_summary_config_text(
    summary_config: Dict[str, Any],
    field_name: str,
) -> str:
    value = summary_config.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "FSMS summary configuration is missing "
            f"'{field_name}'."
        )

    return value.strip()


def _required_business_profile_text(
    business_profile: Dict[str, Any],
    field_name: str,
) -> str:
    value = business_profile.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "Business profile is missing summary field "
            f"'{field_name}'."
        )

    return value.strip()


def _is_business_profile_complete(
    profile: BusinessProfile,
) -> bool:
    required_values = [
        profile.business_name,
        profile.site_name,
        profile.business_type,
        profile.business_description,
    ]

    return all(
        isinstance(value, str) and bool(value.strip())
        for value in required_values
    )


def _format_business_type(
    business_type: Optional[str],
) -> Optional[str]:
    if business_type is None:
        return None

    cleaned = business_type.strip()

    if not cleaned:
        return None

    configured_label = BUSINESS_TYPE_LABELS.get(
        cleaned.lower()
    )

    if configured_label is not None:
        return configured_label

    return (
        cleaned.replace("_", " ")
        .replace("-", " ")
        .capitalize()
    )
