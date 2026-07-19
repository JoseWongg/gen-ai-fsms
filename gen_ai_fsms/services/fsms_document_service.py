import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.schemas.fsms_document import (
    FSMSDocument,
    FSMSDocumentSection,
)
from gen_ai_fsms.services.fsms_document_transformer import (
    build_fsms_document,
    build_supported_control_section,
)
from gen_ai_fsms.services.safety_point_approval_service import (
    get_approved_methods_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
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
                profile_complete=profile_complete,
                screening_complete=screening_complete,
            )
        )

    business_profile_view = {
        "business_name": profile.business_name,
        "site_name": profile.site_name,
        "business_type": _format_business_type(
            profile.business_type
        ),
        "business_description": profile.business_description,
    }

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
    profile_complete: bool,
    screening_complete: bool,
) -> FSMSDocumentSection:
    completion_rule = section_config.get("completion_rule")

    if completion_rule == "business_profile_complete":
        is_complete = profile_complete
        incomplete_message = (
            "Not completed: business profile information is "
            "incomplete."
        )
    elif completion_rule == "food_safety_profile_complete":
        is_complete = profile_complete and screening_complete
        incomplete_message = (
            "Not completed: Food Safety Profile screening is "
            "incomplete."
        )
    else:
        raise ValueError(
            "Unsupported FSMS document summary completion rule: "
            f"'{completion_rule}'."
        )

    return FSMSDocumentSection(
        section_id=section_config["section_id"],
        title=section_config["title"],
        display_order=section_config["display_order"],
        status=(
            "completed"
            if is_complete
            else "not_completed"
        ),
        introduction=section_config["introduction"],
        completion_message=(
            None
            if is_complete
            else incomplete_message
        ),
    )


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
