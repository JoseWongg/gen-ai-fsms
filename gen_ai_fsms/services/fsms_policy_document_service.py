import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from gen_ai_fsms.db.models.business_profile import BusinessProfile
from gen_ai_fsms.schemas.fsms_policy_document import (
    FSMSContentSource,
    FSMSListBlock,
    FSMSPolicyContentBlock,
    FSMSPolicyDocument,
    FSMSPolicySection,
    FSMSPolicySubsection,
    FSMSTextBlock,
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
    Build the new policy document from current stored data.

    This transitional service does not replace the live FSMS
    endpoint or PDF renderer. It currently populates the
    controlled Food Safety Policy content; later implementation
    steps will populate the remaining sections.
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
        profile=profile,
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
    profile: BusinessProfile,
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
                    subsection_config,
                    profile=profile,
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
                        subsection_config,
                        profile=profile,
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
    *,
    profile: BusinessProfile,
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
        content_blocks=_build_configured_content_blocks(
            subsection_config,
            profile=profile,
        ),
    )


def _build_configured_content_blocks(
    configured_object: Dict[str, Any],
    *,
    profile: BusinessProfile,
) -> List[FSMSPolicyContentBlock]:
    definitions = configured_object.get(
        "content_definitions",
        [],
    )

    if not isinstance(definitions, list):
        raise ValueError(
            "Configured FSMS content definitions must "
            "be a list."
        )

    template_values = _policy_template_values(profile)
    content_blocks: List[FSMSPolicyContentBlock] = []

    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError(
                "Each configured FSMS content definition "
                "must be a JSON object."
            )

        block_type = _required_structure_text(
            definition,
            "block_type",
        )
        role = _required_structure_text(
            definition,
            "role",
        )
        source = FSMSContentSource(
            source_references=(
                _configured_source_references(definition)
            )
        )

        if block_type == "text":
            raw_text = definition.get("template")

            if raw_text is None:
                raw_text = definition.get("text")

            if raw_text is None:
                continue

            if (
                not isinstance(raw_text, str)
                or not raw_text.strip()
            ):
                raise ValueError(
                    "Configured FSMS text content must "
                    "be a non-empty string."
                )

            content_blocks.append(
                FSMSTextBlock(
                    role=role,
                    text=_render_policy_template(
                        raw_text,
                        template_values,
                    ),
                    source=source,
                )
            )
            continue

        if block_type == "list":
            configured_items = definition.get("items")

            if configured_items is None:
                continue

            if (
                not isinstance(configured_items, list)
                or not configured_items
            ):
                raise ValueError(
                    "Configured FSMS list content must "
                    "contain at least one item."
                )

            rendered_items = []

            for item in configured_items:
                if (
                    not isinstance(item, str)
                    or not item.strip()
                ):
                    raise ValueError(
                        "Each configured FSMS list item "
                        "must be a non-empty string."
                    )

                rendered_items.append(
                    _render_policy_template(
                        item,
                        template_values,
                    )
                )

            content_blocks.append(
                FSMSListBlock(
                    role=role,
                    items=rendered_items,
                    source=source,
                )
            )
            continue

        raise ValueError(
            "Unsupported configured FSMS content block "
            f"type: '{block_type}'."
        )

    return content_blocks


def _policy_template_values(
    profile: BusinessProfile,
) -> Dict[str, str]:
    return {
        "business_name": _required_profile_text(
            profile,
            "business_name",
        ),
        "site_name": _required_profile_text(
            profile,
            "site_name",
        ),
        "business_type_with_article": (
            _business_type_with_article(
                getattr(profile, "business_type", None)
            )
        ),
    }


def _render_policy_template(
    template: str,
    values: Dict[str, str],
) -> str:
    try:
        rendered = template.strip().format_map(values)
    except KeyError as error:
        missing_value = error.args[0]
        raise ValueError(
            "FSMS policy content template refers to "
            f"unknown value '{missing_value}'."
        ) from error

    if not rendered:
        raise ValueError(
            "Rendered FSMS policy content must not "
            "be empty."
        )

    return rendered


def _configured_source_references(
    definition: Dict[str, Any],
) -> List[str]:
    references = definition.get(
        "source_references",
        [],
    )

    if not isinstance(references, list):
        raise ValueError(
            "Configured FSMS source references must "
            "be a list."
        )

    cleaned_references = []

    for reference in references:
        if (
            not isinstance(reference, str)
            or not reference.strip()
        ):
            raise ValueError(
                "Each configured FSMS source reference "
                "must be a non-empty string."
            )

        cleaned_references.append(reference.strip())

    return cleaned_references


def _business_type_with_article(
    business_type: Optional[str],
) -> str:
    formatted_type = _format_business_type(
        business_type
    )

    if (
        formatted_type is None
        or formatted_type.lower() == "other"
    ):
        return "a food business"

    article = (
        "an"
        if formatted_type[0].lower() in "aeiou"
        else "a"
    )

    return f"{article} {formatted_type.lower()}"


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
