import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocument,
    FSMSPolicySection,
    FSMSPolicySubsection,
)
from gen_ai_fsms.services.safety_point_approval_service import (
    get_approved_methods_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
)


FSMS_POLICY_DOCUMENT_STRUCTURE_PATH = Path(
    "data/fsms_policy_document_structure.json"
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


def load_fsms_policy_document_structure(
    path: Path = FSMS_POLICY_DOCUMENT_STRUCTURE_PATH,
) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            "FSMS policy document structure file not found: "
            f"{path}"
        )

    structure = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(structure, dict):
        raise ValueError(
            "FSMS policy document structure must contain "
            "a JSON object."
        )

    return structure


def generate_fsms_policy_document_for_profile(
    *,
    db: Session,
    business_profile_id: int,
    generated_at: Optional[datetime] = None,
    structure_config: Optional[Dict[str, Any]] = None,
) -> FSMSPolicyDocument:
    """
    Build the new policy-document shell from current stored data.

    This transitional service does not replace the live FSMS
    endpoint or PDF renderer. Later implementation steps will
    populate the section content blocks.
    """
    profile = (
        db.query(BusinessProfile)
        .filter(
            BusinessProfile.id == business_profile_id
        )
        .first()
    )

    if profile is None:
        raise ValueError(
            "Business profile not found: "
            f"{business_profile_id}."
        )

    structure = (
        structure_config
        if structure_config is not None
        else load_fsms_policy_document_structure()
    )

    configured_sections = structure.get("sections")

    if not isinstance(configured_sections, list):
        raise ValueError(
            "FSMS policy document structure must contain "
            "a section list."
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

    applicable_ids = _safety_point_ids(
        applicable_safety_points,
        source_name="applicable",
    )
    approved_ids = _safety_point_ids(
        approved_safety_points,
        source_name="approved",
    )

    approved_applicable_points = [
        safety_point
        for safety_point in applicable_safety_points
        if safety_point["safety_point_id"]
        in approved_ids
    ]

    profile_complete = _is_business_profile_complete(
        profile
    )
    screening_complete = (
        screening_status.get("is_complete") is True
    )
    all_applicable_points_approved = (
        applicable_ids.issubset(approved_ids)
    )

    document_status = (
        "approved"
        if (
            profile_complete
            and screening_complete
            and all_applicable_points_approved
        )
        else "draft"
    )

    draft_notice = None

    if document_status == "draft":
        draft_notice = _required_structure_text(
            structure,
            "draft_notice",
        )

    sections = _build_policy_sections(
        configured_sections=configured_sections,
        approved_applicable_points=(
            approved_applicable_points
        ),
    )

    return FSMSPolicyDocument(
        document_title=_required_structure_text(
            structure,
            "document_title",
        ),
        document_status=document_status,
        draft_notice=draft_notice,
        business_name=_required_profile_text(
            profile,
            "business_name",
        ),
        site_name=_required_profile_text(
            profile,
            "site_name",
        ),
        business_type=_format_business_type(
            profile.business_type
        ),
        generated_at=(
            generated_at
            if generated_at is not None
            else datetime.now(timezone.utc)
        ),
        sections=sections,
    )


def _build_policy_sections(
    *,
    configured_sections: List[Dict[str, Any]],
    approved_applicable_points: List[
        Dict[str, Any]
    ],
) -> List[FSMSPolicySection]:
    approved_points_by_section: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    for safety_point in approved_applicable_points:
        section_id = safety_point.get("section_id")

        if not isinstance(section_id, str):
            raise ValueError(
                "An approved applicable safety point is "
                "missing its source section ID."
            )

        approved_points_by_section.setdefault(
            section_id,
            [],
        ).append(safety_point)

    sections = []

    for section_config in configured_sections:
        inclusion = section_config.get("inclusion")
        source_section_ids = section_config.get(
            "source_section_ids",
            [],
        )

        if inclusion in {
            "always",
            "business_profile_exists",
        }:
            subsections = [
                _build_policy_subsection(
                    subsection_config
                )
                for subsection_config
                in _configured_subsections(
                    section_config
                )
            ]
        elif inclusion == "approved_applicable_content":
            section_points = [
                safety_point
                for source_section_id in source_section_ids
                for safety_point
                in approved_points_by_section.get(
                    source_section_id,
                    [],
                )
            ]

            if not section_points:
                continue

            approved_safe_method_ids = {
                _required_safety_point_text(
                    safety_point,
                    "safe_method_id",
                )
                for safety_point in section_points
            }

            subsections = []

            for subsection_config in (
                _configured_subsections(section_config)
            ):
                if (
                    subsection_config.get("inclusion")
                    != "approved_applicable_content"
                ):
                    continue

                configured_method_ids = {
                    str(value).strip()
                    for value in subsection_config.get(
                        "source_safe_method_ids",
                        [],
                    )
                    if str(value).strip()
                }

                if not (
                    configured_method_ids
                    & approved_safe_method_ids
                ):
                    continue

                subsections.append(
                    _build_policy_subsection(
                        subsection_config
                    )
                )

            if not subsections:
                continue
        else:
            raise ValueError(
                "Unsupported FSMS policy section "
                f"inclusion rule: '{inclusion}'."
            )

        sections.append(
            FSMSPolicySection(
                section_number=(
                    _required_structure_text(
                        section_config,
                        "section_number",
                    )
                ),
                title=_required_structure_text(
                    section_config,
                    "title",
                ),
                subsections=subsections,
            )
        )

    return sections


def _configured_subsections(
    section_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    subsections = section_config.get("subsections")

    if not isinstance(subsections, list):
        raise ValueError(
            "Each FSMS policy section must contain "
            "a subsection list."
        )

    return subsections


def _build_policy_subsection(
    subsection_config: Dict[str, Any],
) -> FSMSPolicySubsection:
    return FSMSPolicySubsection(
        subsection_number=_required_structure_text(
            subsection_config,
            "subsection_number",
        ),
        title=_required_structure_text(
            subsection_config,
            "title",
        ),
    )


def _safety_point_ids(
    safety_points: List[Dict[str, Any]],
    *,
    source_name: str,
) -> Set[str]:
    safety_point_ids = set()

    for safety_point in safety_points:
        if not isinstance(safety_point, dict):
            raise ValueError(
                f"Each {source_name} safety point must "
                "be a JSON object."
            )

        safety_point_ids.add(
            _required_safety_point_text(
                safety_point,
                "safety_point_id",
            )
        )

    return safety_point_ids


def _required_safety_point_text(
    safety_point: Dict[str, Any],
    field_name: str,
) -> str:
    value = safety_point.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "Safety point data is missing "
            f"'{field_name}'."
        )

    return value.strip()


def _required_structure_text(
    configured_object: Dict[str, Any],
    field_name: str,
) -> str:
    value = configured_object.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "FSMS policy document structure is missing "
            f"'{field_name}'."
        )

    return value.strip()


def _required_profile_text(
    profile: BusinessProfile,
    field_name: str,
) -> str:
    value = getattr(profile, field_name, None)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            "Business profile is missing required field "
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
