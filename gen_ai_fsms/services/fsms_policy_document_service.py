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
    get_condition_values_for_profile,
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
    controlled Food Safety Policy, Business Scope and approved
    chilling-control content. Later implementation steps will
    populate equipment monitoring and cooking controls.
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
    condition_values = get_condition_values_for_profile(
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

    approved_points_by_id = {}

    for approved_safety_point in approved_safety_points:
        approved_id = _required_safety_point_text(
            approved_safety_point,
            "safety_point_id",
        )
        approved_points_by_id.setdefault(
            approved_id,
            approved_safety_point,
        )

    approved_applicable_points = []

    for safety_point in applicable_safety_points:
        safety_point_id = _required_safety_point_text(
            safety_point,
            "safety_point_id",
        )
        approval = approved_points_by_id.get(
            safety_point_id
        )

        if approval is None:
            continue

        merged_safety_point = dict(safety_point)
        merged_safety_point["_approval"] = approval
        approved_applicable_points.append(
            merged_safety_point
        )

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
        applicable_safety_points=applicable_safety_points,
        condition_values=condition_values,
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
    applicable_safety_points: List[
        Dict[str, Any]
    ],
    condition_values: Dict[str, str],
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
        section_content_blocks = []

        if inclusion in {
            "always",
            "business_profile_exists",
        }:
            if (
                section_config.get("section_id")
                == (
                    "business_scope_and_"
                    "food_safety_overview"
                )
            ):
                subsections = (
                    _build_business_scope_subsections(
                        section_config=section_config,
                        profile=profile,
                        condition_values=condition_values,
                        applicable_safety_points=(
                            applicable_safety_points
                        ),
                    )
                )
            else:
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

            if (
                section_config.get("section_id")
                == "chilling_and_temperature_control"
            ):
                section_content_blocks = (
                    _build_configured_content_blocks(
                        section_config,
                        profile=profile,
                    )
                )
                subsections = (
                    _build_chilling_operational_subsections(
                        section_config=section_config,
                        profile=profile,
                        safety_points=section_points,
                    )
                )
            else:
                approved_safe_method_ids = {
                    _required_safety_point_text(
                        safety_point,
                        "safe_method_id",
                    )
                    for safety_point in section_points
                }
                subsections = []

                for subsection_config in (
                    _configured_subsections(
                        section_config
                    )
                ):
                    if (
                        subsection_config.get(
                            "inclusion"
                        )
                        != "approved_applicable_content"
                    ):
                        continue

                    configured_method_ids = {
                        str(value).strip()
                        for value
                        in subsection_config.get(
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
                content_blocks=section_content_blocks,
                subsections=subsections,
            )
        )

    return sections


def _build_chilling_operational_subsections(
    *,
    section_config: Dict[str, Any],
    profile: BusinessProfile,
    safety_points: List[Dict[str, Any]],
) -> List[FSMSPolicySubsection]:
    subsections = []

    for subsection_config in _configured_subsections(
        section_config
    ):
        if (
            subsection_config.get("inclusion")
            != "approved_applicable_content"
        ):
            continue

        configured_method_ids = set(
            _configured_string_list(
                subsection_config,
                "source_safe_method_ids",
            )
        )
        subsection_points = [
            safety_point
            for safety_point in safety_points
            if _required_safety_point_text(
                safety_point,
                "safe_method_id",
            )
            in configured_method_ids
        ]

        if not subsection_points:
            continue

        subsections.append(
            _build_operational_subsection(
                subsection_config=subsection_config,
                profile=profile,
                safety_points=subsection_points,
            )
        )

    return subsections


def _build_operational_subsection(
    *,
    subsection_config: Dict[str, Any],
    profile: BusinessProfile,
    safety_points: List[Dict[str, Any]],
) -> FSMSPolicySubsection:
    definitions = subsection_config.get(
        "content_definitions"
    )

    if not isinstance(definitions, list):
        raise ValueError(
            "Operational FSMS subsections must contain "
            "a content definition list."
        )

    content_blocks: List[
        FSMSPolicyContentBlock
    ] = []

    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError(
                "Each operational FSMS content "
                "definition must be a JSON object."
            )

        dynamic_sources = definition.get(
            "dynamic_sources",
            [],
        )

        if not isinstance(dynamic_sources, list):
            raise ValueError(
                "Operational FSMS dynamic sources must "
                "be a list."
            )

        if (
            "approved_safety_point_instructions"
            in dynamic_sources
        ):
            content_blocks.append(
                _build_operational_procedure_block(
                    definition=definition,
                    safety_points=safety_points,
                )
            )
            continue

        if (
            "approved_additional_responses"
            in dynamic_sources
        ):
            content_blocks.extend(
                _build_additional_response_blocks(
                    definition=definition,
                    safety_points=safety_points,
                )
            )
            continue

        required_safety_point_ids = set(
            _configured_string_list(
                definition,
                "source_safety_point_ids",
            )
        )
        source_points = safety_points

        if required_safety_point_ids:
            source_points = [
                safety_point
                for safety_point in safety_points
                if _required_safety_point_text(
                    safety_point,
                    "safety_point_id",
                )
                in required_safety_point_ids
            ]

            if not source_points:
                continue

        raw_text = definition.get("template")

        if raw_text is None:
            raw_text = definition.get("text")

        if (
            not isinstance(raw_text, str)
            or not raw_text.strip()
        ):
            raise ValueError(
                "Operational FSMS text content must "
                "be a non-empty string."
            )

        heading = definition.get("heading")

        if heading is not None:
            heading = _required_structure_text(
                definition,
                "heading",
            )

        content_blocks.append(
            FSMSTextBlock(
                role=_required_structure_text(
                    definition,
                    "role",
                ),
                heading=heading,
                text=_render_policy_template(
                    raw_text,
                    _policy_template_values(profile),
                ),
                source=_operational_content_source(
                    safety_points=source_points,
                    definition=definition,
                ),
            )
        )

    return FSMSPolicySubsection(
        subsection_number=_required_structure_text(
            subsection_config,
            "subsection_number",
        ),
        title=_required_structure_text(
            subsection_config,
            "title",
        ),
        content_blocks=content_blocks,
    )


def _build_operational_procedure_block(
    *,
    definition: Dict[str, Any],
    safety_points: List[Dict[str, Any]],
) -> FSMSListBlock:
    items = [
        _normalise_operational_text(
            _required_safety_point_text(
                safety_point,
                "instruction",
            )
        )
        for safety_point in safety_points
    ]

    return FSMSListBlock(
        role=_required_structure_text(
            definition,
            "role",
        ),
        items=items,
        source=_operational_content_source(
            safety_points=safety_points,
            definition=definition,
        ),
    )


def _build_additional_response_blocks(
    *,
    definition: Dict[str, Any],
    safety_points: List[Dict[str, Any]],
) -> List[FSMSTextBlock]:
    blocks = []
    heading = definition.get("heading")

    if heading is not None:
        heading = _required_structure_text(
            definition,
            "heading",
        )

    for safety_point in safety_points:
        approval = safety_point.get("_approval", {})
        responses = approval.get(
            "additional_responses",
            [],
        )

        if not isinstance(responses, list):
            raise ValueError(
                "Approved safety point responses must "
                "be a list."
            )

        for response in responses:
            if not isinstance(response, dict):
                raise ValueError(
                    "Each approved safety point response "
                    "must be a JSON object."
                )

            document_response_text = response.get(
                "document_response_text"
            )

            if (
                not isinstance(
                    document_response_text,
                    str,
                )
                or not document_response_text.strip()
            ):
                continue

            question_key = _required_structure_text(
                response,
                "question_key",
            )

            blocks.append(
                FSMSTextBlock(
                    role=_required_structure_text(
                        definition,
                        "role",
                    ),
                    heading=heading,
                    text=_normalise_operational_text(
                        document_response_text
                    ),
                    source=FSMSContentSource(
                        safety_point_ids=[
                            _required_safety_point_text(
                                safety_point,
                                "safety_point_id",
                            )
                        ],
                        additional_question_keys=[
                            question_key
                        ],
                        source_references=(
                            _operational_source_references(
                                [safety_point],
                                definition=definition,
                            )
                        ),
                    ),
                )
            )

    return blocks


def _operational_content_source(
    *,
    safety_points: List[Dict[str, Any]],
    definition: Dict[str, Any],
) -> FSMSContentSource:
    return FSMSContentSource(
        safety_point_ids=[
            _required_safety_point_text(
                safety_point,
                "safety_point_id",
            )
            for safety_point in safety_points
        ],
        source_references=(
            _operational_source_references(
                safety_points,
                definition=definition,
            )
        ),
    )


def _operational_source_references(
    safety_points: List[Dict[str, Any]],
    *,
    definition: Dict[str, Any],
) -> List[str]:
    references = []

    for reference in _configured_source_references(
        definition
    ):
        _append_unique(references, reference)

    for safety_point in safety_points:
        for field_name in [
            "source_references",
            "additional_source_references",
        ]:
            for reference in _configured_string_list(
                safety_point,
                field_name,
            ):
                _append_unique(
                    references,
                    reference,
                )

        approval = safety_point.get("_approval", {})

        if isinstance(approval, dict):
            for reference in _configured_string_list(
                approval,
                "provenance_references",
            ):
                _append_unique(
                    references,
                    reference,
                )

    return references


def _normalise_operational_text(value: str) -> str:
    cleaned = " ".join(value.split())

    if not cleaned:
        raise ValueError(
            "Operational FSMS content must not be empty."
        )

    return cleaned


def _build_business_scope_subsections(
    *,
    section_config: Dict[str, Any],
    profile: BusinessProfile,
    condition_values: Dict[str, str],
    applicable_safety_points: List[
        Dict[str, Any]
    ],
) -> List[FSMSPolicySubsection]:
    subsections = []

    for subsection_config in _configured_subsections(
        section_config
    ):
        subsection_id = _required_structure_text(
            subsection_config,
            "subsection_id",
        )

        if subsection_id == "activities_covered_by_fsms":
            content_blocks = _build_activity_blocks(
                subsection_config=subsection_config,
                profile=profile,
                condition_values=condition_values,
            )
        elif subsection_id == "main_food_safety_hazards":
            content_blocks = _build_hazard_blocks(
                subsection_config=subsection_config,
                profile=profile,
                condition_values=condition_values,
                applicable_safety_points=(
                    applicable_safety_points
                ),
            )
        else:
            content_blocks = (
                _build_configured_content_blocks(
                    subsection_config,
                    profile=profile,
                )
            )

        if not content_blocks:
            continue

        subsections.append(
            FSMSPolicySubsection(
                subsection_number=(
                    _required_structure_text(
                        subsection_config,
                        "subsection_number",
                    )
                ),
                title=_required_structure_text(
                    subsection_config,
                    "title",
                ),
                content_blocks=content_blocks,
            )
        )

    return subsections


def _build_activity_blocks(
    *,
    subsection_config: Dict[str, Any],
    profile: BusinessProfile,
    condition_values: Dict[str, str],
) -> List[FSMSPolicyContentBlock]:
    definitions = _definitions_by_content_key(
        subsection_config
    )
    activity_definition = definitions[
        "applicable_activity_statements"
    ]
    mappings = activity_definition.get(
        "condition_statements"
    )

    if not isinstance(mappings, list):
        raise ValueError(
            "Configured FSMS activity statements must "
            "be a list."
        )

    items = []
    matched_condition_ids = []

    for mapping in mappings:
        if not isinstance(mapping, dict):
            raise ValueError(
                "Each configured FSMS activity statement "
                "must be a JSON object."
            )

        condition_id = _required_structure_text(
            mapping,
            "condition_id",
        )

        if condition_values.get(condition_id) != "true":
            continue

        items.append(
            _required_structure_text(
                mapping,
                "statement",
            )
        )
        matched_condition_ids.append(condition_id)

    if not items:
        return []

    introduction_blocks = (
        _build_single_configured_definition(
            definitions["activities_introduction"],
            profile=profile,
        )
    )

    return introduction_blocks + [
        FSMSListBlock(
            role=_required_structure_text(
                activity_definition,
                "role",
            ),
            items=items,
            source=FSMSContentSource(
                condition_ids=matched_condition_ids,
                source_references=(
                    _configured_source_references(
                        activity_definition
                    )
                ),
            ),
        )
    ]


def _build_hazard_blocks(
    *,
    subsection_config: Dict[str, Any],
    profile: BusinessProfile,
    condition_values: Dict[str, str],
    applicable_safety_points: List[
        Dict[str, Any]
    ],
) -> List[FSMSPolicyContentBlock]:
    definitions = _definitions_by_content_key(
        subsection_config
    )
    hazard_definition = definitions[
        "applicable_hazard_summary"
    ]
    configured_hazards = hazard_definition.get(
        "hazard_definitions"
    )

    if not isinstance(configured_hazards, list):
        raise ValueError(
            "Configured FSMS hazard definitions must "
            "be a list."
        )

    items = []
    matched_condition_ids = []
    matched_safety_point_ids = []

    for configured_hazard in configured_hazards:
        if not isinstance(configured_hazard, dict):
            raise ValueError(
                "Each configured FSMS hazard definition "
                "must be a JSON object."
            )

        condition_ids = _configured_string_list(
            configured_hazard,
            "condition_ids",
        )
        safe_method_ids = set(
            _configured_string_list(
                configured_hazard,
                "safe_method_ids",
            )
        )

        hazard_condition_ids = [
            condition_id
            for condition_id in condition_ids
            if condition_values.get(condition_id) == "true"
        ]

        hazard_safety_points = [
            safety_point
            for safety_point in applicable_safety_points
            if (
                _required_safety_point_text(
                    safety_point,
                    "safe_method_id",
                )
                in safe_method_ids
            )
        ]

        if (
            not hazard_condition_ids
            and not hazard_safety_points
        ):
            continue

        items.append(
            _required_structure_text(
                configured_hazard,
                "statement",
            )
        )

        for condition_id in hazard_condition_ids:
            _append_unique(
                matched_condition_ids,
                condition_id,
            )

        for safety_point in hazard_safety_points:
            _append_unique(
                matched_safety_point_ids,
                _required_safety_point_text(
                    safety_point,
                    "safety_point_id",
                ),
            )

    if not items:
        return []

    introduction_blocks = (
        _build_single_configured_definition(
            definitions["hazards_introduction"],
            profile=profile,
        )
    )

    return introduction_blocks + [
        FSMSListBlock(
            role=_required_structure_text(
                hazard_definition,
                "role",
            ),
            items=items,
            source=FSMSContentSource(
                safety_point_ids=(
                    matched_safety_point_ids
                ),
                condition_ids=matched_condition_ids,
                source_references=(
                    _configured_source_references(
                        hazard_definition
                    )
                ),
            ),
        )
    ]


def _definitions_by_content_key(
    configured_object: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    definitions = configured_object.get(
        "content_definitions"
    )

    if not isinstance(definitions, list):
        raise ValueError(
            "Configured FSMS content definitions must "
            "be a list."
        )

    definitions_by_key = {}

    for definition in definitions:
        if not isinstance(definition, dict):
            raise ValueError(
                "Each configured FSMS content definition "
                "must be a JSON object."
            )

        content_key = _required_structure_text(
            definition,
            "content_key",
        )
        definitions_by_key[content_key] = definition

    return definitions_by_key


def _build_single_configured_definition(
    definition: Dict[str, Any],
    *,
    profile: BusinessProfile,
) -> List[FSMSPolicyContentBlock]:
    return _build_configured_content_blocks(
        {
            "content_definitions": [
                definition,
            ]
        },
        profile=profile,
    )


def _configured_string_list(
    configured_object: Dict[str, Any],
    field_name: str,
) -> List[str]:
    values = configured_object.get(
        field_name,
        [],
    )

    if not isinstance(values, list):
        raise ValueError(
            "Configured FSMS field "
            f"'{field_name}' must be a list."
        )

    cleaned_values = []

    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                "Each configured FSMS value in "
                f"'{field_name}' must be a non-empty "
                "string."
            )

        cleaned_values.append(value.strip())

    return cleaned_values


def _append_unique(
    values: List[str],
    value: str,
) -> None:
    if value not in values:
        values.append(value)


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

        if not _profile_fields_are_available(
            definition,
            profile=profile,
        ):
            continue

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
        "business_description_sentence": (
            _normalise_optional_sentence(
                getattr(
                    profile,
                    "business_description",
                    None,
                )
            )
        ),
    }


def _profile_fields_are_available(
    definition: Dict[str, Any],
    *,
    profile: BusinessProfile,
) -> bool:
    field_names = definition.get(
        "required_profile_fields",
        [],
    )

    if not isinstance(field_names, list):
        raise ValueError(
            "Configured required profile fields must "
            "be a list."
        )

    for field_name in field_names:
        if (
            not isinstance(field_name, str)
            or not field_name.strip()
        ):
            raise ValueError(
                "Each required profile field must be "
                "a non-empty string."
            )

        value = getattr(
            profile,
            field_name.strip(),
            None,
        )

        if (
            not isinstance(value, str)
            or not value.strip()
        ):
            return False

    return True


def _normalise_optional_sentence(
    value: Optional[str],
) -> str:
    if not isinstance(value, str):
        return ""

    cleaned = value.strip()

    if not cleaned:
        return ""

    if cleaned[-1] not in ".!?":
        cleaned = f"{cleaned}."

    return cleaned


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
