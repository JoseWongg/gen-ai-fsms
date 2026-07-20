from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSPolicyDocumentProgress,
)
from gen_ai_fsms.services.fsms_policy_document_service import (
    load_fsms_policy_document_structure,
)
from gen_ai_fsms.services.safety_point_approval_service import (
    get_approved_methods_for_profile,
    get_relevant_safety_points_for_profile,
    get_screening_completion_status,
)


BEYOND_SCOPE_INCLUSION = (
    "beyond_current_project_scope"
)
FOUNDATION_INCLUSIONS = {
    "always",
    "business_profile_exists",
}
OPERATIONAL_INCLUSION = "approved_applicable_content"


def generate_fsms_policy_document_progress_for_profile(
    *,
    db: Session,
    business_profile_id: int,
    structure_config: Optional[Dict[str, Any]] = None,
) -> FSMSPolicyDocumentProgress:
    """
    Calculate live FSMS policy completion for one business.

    The calculation performs no database writes and does
    not alter the generated policy document.
    """
    structure = (
        structure_config
        if structure_config is not None
        else load_fsms_policy_document_structure()
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

    return calculate_fsms_policy_document_progress(
        structure_config=structure,
        screening_complete=(
            screening_status.get("is_complete") is True
        ),
        applicable_safety_points=(
            applicable_safety_points
        ),
        approved_safety_points=(
            approved_safety_points
        ),
    )


def calculate_fsms_policy_document_progress(
    *,
    structure_config: Dict[str, Any],
    screening_complete: bool,
    applicable_safety_points: List[Dict[str, Any]],
    approved_safety_points: List[Dict[str, Any]],
) -> FSMSPolicyDocumentProgress:
    """
    Calculate business completion and product coverage.

    Sections beyond the current project scope contribute
    to product coverage only. Supported operational
    sections are excluded from the business denominator
    when they are not applicable to the business.
    """
    configured_sections = structure_config.get(
        "sections"
    )

    if not isinstance(configured_sections, list):
        raise ValueError(
            "FSMS policy document structure must contain "
            "a section list."
        )

    applicable_ids_by_source_section = (
        _applicable_ids_by_source_section(
            applicable_safety_points
        )
    )
    approved_ids = _safety_point_ids(
        approved_safety_points,
        source_name="approved",
    )

    planned_section_count = len(configured_sections)
    supported_section_count = 0
    applicable_supported_count = 0
    completed_applicable_count = 0

    for section_config in configured_sections:
        if not isinstance(section_config, dict):
            raise ValueError(
                "Each FSMS policy section configuration "
                "must be a JSON object."
            )

        inclusion = section_config.get("inclusion")

        if inclusion == BEYOND_SCOPE_INCLUSION:
            continue

        supported_section_count += 1

        if inclusion in FOUNDATION_INCLUSIONS:
            applicable_supported_count += 1

            if screening_complete:
                completed_applicable_count += 1

            continue

        if inclusion == OPERATIONAL_INCLUSION:
            source_section_ids = (
                _configured_source_section_ids(
                    section_config
                )
            )
            section_applicable_ids: Set[str] = set()

            for source_section_id in source_section_ids:
                section_applicable_ids.update(
                    applicable_ids_by_source_section.get(
                        source_section_id,
                        set(),
                    )
                )

            if not section_applicable_ids:
                continue

            applicable_supported_count += 1

            if section_applicable_ids.issubset(
                approved_ids
            ):
                completed_applicable_count += 1

            continue

        raise ValueError(
            "Unsupported current FSMS policy section "
            f"inclusion rule: '{inclusion}'."
        )

    completion_percentage = _completion_percentage(
        completed_count=completed_applicable_count,
        applicable_count=applicable_supported_count,
    )
    document_status = _progress_status(
        completed_count=completed_applicable_count,
        applicable_count=applicable_supported_count,
    )

    return FSMSPolicyDocumentProgress(
        screening_complete=screening_complete,
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
        main_value=f"{completion_percentage}%",
        completion_caption=(
            (
                f"{completed_applicable_count} of "
                f"{applicable_supported_count} current "
                "sections complete"
            )
            if screening_complete
            else "Food Safety Profile not completed"
        ),
        coverage_caption=(
            f"{supported_section_count} of "
            f"{planned_section_count} planned sections "
            "supported"
        ),
    )


def _applicable_ids_by_source_section(
    safety_points: List[Dict[str, Any]],
) -> Dict[str, Set[str]]:
    if not isinstance(safety_points, list):
        raise ValueError(
            "Applicable safety point data must be a list."
        )

    result: Dict[str, Set[str]] = {}

    for safety_point in safety_points:
        if not isinstance(safety_point, dict):
            raise ValueError(
                "Each applicable safety point must be "
                "a JSON object."
            )

        safety_point_id = _required_safety_point_text(
            safety_point,
            "safety_point_id",
            source_name="applicable",
        )
        source_section_id = _required_safety_point_text(
            safety_point,
            "section_id",
            source_name="applicable",
        )

        result.setdefault(
            source_section_id,
            set(),
        ).add(safety_point_id)

    return result


def _safety_point_ids(
    safety_points: List[Dict[str, Any]],
    *,
    source_name: str,
) -> Set[str]:
    if not isinstance(safety_points, list):
        raise ValueError(
            f"{source_name.capitalize()} safety point "
            "data must be a list."
        )

    return {
        _required_safety_point_text(
            safety_point,
            "safety_point_id",
            source_name=source_name,
        )
        for safety_point in safety_points
    }


def _required_safety_point_text(
    safety_point: Dict[str, Any],
    field_name: str,
    *,
    source_name: str,
) -> str:
    if not isinstance(safety_point, dict):
        raise ValueError(
            f"Each {source_name} safety point must be "
            "a JSON object."
        )

    value = safety_point.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"An {source_name} safety point is missing "
            f"'{field_name}'."
        )

    return value.strip()


def _configured_source_section_ids(
    section_config: Dict[str, Any],
) -> List[str]:
    values = section_config.get(
        "source_section_ids"
    )

    if (
        not isinstance(values, list)
        or not values
        or not all(
            isinstance(value, str)
            and bool(value.strip())
            for value in values
        )
    ):
        raise ValueError(
            "An operational FSMS policy section must "
            "define source section IDs."
        )

    return [
        value.strip()
        for value in values
    ]


def _completion_percentage(
    *,
    completed_count: int,
    applicable_count: int,
) -> int:
    if applicable_count == 0:
        return 0

    return round(
        completed_count
        / applicable_count
        * 100
    )


def _progress_status(
    *,
    completed_count: int,
    applicable_count: int,
) -> str:
    if completed_count == 0:
        return "not_started"

    if completed_count == applicable_count:
        return "completed"

    return "in_progress"
