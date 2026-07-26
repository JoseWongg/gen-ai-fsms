from types import SimpleNamespace

import pytest

from gen_ai_fsms.services import (
    fsms_policy_document_service as service,
)


PROFILE_INCOMPLETE_NOTICE = (
    "Not completed. Complete the Food Safety Profile "
    "to determine which controls apply to this section."
)

UNAPPROVED_NOTICE = (
    "Not completed. The relevant safety points have "
    "not yet been approved."
)

PARTIAL_NOTICE = (
    "Not completed. Some relevant safety points have "
    "not yet been approved."
)


def _profile():
    return SimpleNamespace(
        business_name="Example Foods Ltd",
        site_name="Example Kitchen",
        business_type="bakery",
        business_description=(
            "A bakery making chilled desserts."
        ),
    )


def _safety_point(
    safety_point_id,
    section_id,
    safe_method_id,
):
    return {
        "safety_point_id": safety_point_id,
        "section_id": section_id,
        "safe_method_id": safe_method_id,
    }


def _structure():
    return [
        {
            "section_id": "foundation",
            "section_number": "1",
            "title": "Foundation",
            "inclusion": "always",
            "subsections": [],
        },
        {
            "section_id": "operational_alpha",
            "section_number": "2",
            "title": "Operational Alpha",
            "inclusion": (
                "approved_applicable_content"
            ),
            "source_section_ids": ["alpha"],
            "subsections": [
                {
                    "subsection_id": "alpha_one",
                    "subsection_number": "2.1",
                    "title": "Alpha One",
                    "inclusion": (
                        "approved_applicable_content"
                    ),
                    "source_safe_method_ids": [
                        "A.1"
                    ],
                },
                {
                    "subsection_id": "alpha_two",
                    "subsection_number": "2.2",
                    "title": "Alpha Two",
                    "inclusion": (
                        "approved_applicable_content"
                    ),
                    "source_safe_method_ids": [
                        "A.2"
                    ],
                },
            ],
        },
        {
            "section_id": "operational_beta",
            "section_number": "3",
            "title": "Operational Beta",
            "inclusion": (
                "approved_applicable_content"
            ),
            "source_section_ids": ["beta"],
            "subsections": [
                {
                    "subsection_id": "beta_one",
                    "subsection_number": "3.1",
                    "title": "Beta One",
                    "inclusion": (
                        "approved_applicable_content"
                    ),
                    "source_safe_method_ids": [
                        "B.1"
                    ],
                },
            ],
        },
        {
            "section_id": "future_section",
            "section_number": "4",
            "title": "Future Section",
            "inclusion": (
                "beyond_current_project_scope"
            ),
            "content_definitions": [
                {
                    "content_key": "future_notice",
                    "block_type": "text",
                    "role": "introduction",
                    "text": (
                        "Beyond current project scope."
                    ),
                },
            ],
            "subsections": [],
        },
    ]


def _build(
    *,
    screening_complete,
    applicable=None,
    approved=None,
):
    return service._build_policy_sections(
        configured_sections=_structure(),
        approved_applicable_points=approved or [],
        profile=_profile(),
        applicable_safety_points=applicable or [],
        condition_values={},
        active_chilling_equipment=[],
        screening_complete=screening_complete,
    )


def _section(sections, title):
    return next(
        section
        for section in sections
        if section.title == title
    )


def _notice_texts(section):
    return [
        block.text
        for block in section.content_blocks
        if block.block_type == "text"
    ]


def test_incomplete_screening_keeps_operational_sections():
    sections = _build(screening_complete=False)

    assert [section.title for section in sections] == [
        "Foundation",
        "Operational Alpha",
        "Operational Beta",
        "Future Section",
    ]

    assert _notice_texts(
        _section(sections, "Operational Alpha")
    ) == [PROFILE_INCOMPLETE_NOTICE]

    assert _notice_texts(
        _section(sections, "Operational Beta")
    ) == [PROFILE_INCOMPLETE_NOTICE]


def test_completed_screening_excludes_non_applicable_sections():
    sections = _build(screening_complete=True)

    assert [section.title for section in sections] == [
        "Foundation",
        "Future Section",
    ]


def test_applicable_unapproved_section_remains_visible():
    applicable = [
        _safety_point(
            "A.1.1",
            "alpha",
            "A.1",
        )
    ]

    sections = _build(
        screening_complete=True,
        applicable=applicable,
    )

    alpha = _section(
        sections,
        "Operational Alpha",
    )

    assert alpha.subsections == []
    assert _notice_texts(alpha) == [
        UNAPPROVED_NOTICE
    ]


def test_partially_approved_section_keeps_approved_content():
    applicable = [
        _safety_point(
            "A.1.1",
            "alpha",
            "A.1",
        ),
        _safety_point(
            "A.2.1",
            "alpha",
            "A.2",
        ),
    ]

    sections = _build(
        screening_complete=True,
        applicable=applicable,
        approved=[applicable[0]],
    )

    alpha = _section(
        sections,
        "Operational Alpha",
    )

    assert [
        subsection.title
        for subsection in alpha.subsections
    ] == ["Alpha One"]

    assert _notice_texts(alpha) == [
        PARTIAL_NOTICE
    ]


def test_fully_approved_section_has_no_incomplete_notice():
    applicable = [
        _safety_point(
            "A.1.1",
            "alpha",
            "A.1",
        ),
        _safety_point(
            "A.2.1",
            "alpha",
            "A.2",
        ),
    ]

    sections = _build(
        screening_complete=True,
        applicable=applicable,
        approved=applicable,
    )

    alpha = _section(
        sections,
        "Operational Alpha",
    )

    assert [
        subsection.title
        for subsection in alpha.subsections
    ] == [
        "Alpha One",
        "Alpha Two",
    ]

    assert _notice_texts(alpha) == []


def test_same_rules_apply_to_another_operational_section():
    beta_point = _safety_point(
        "B.1.1",
        "beta",
        "B.1",
    )

    sections = _build(
        screening_complete=True,
        applicable=[beta_point],
    )

    assert [
        section.title
        for section in sections
    ] == [
        "Foundation",
        "Operational Beta",
        "Future Section",
    ]

    assert _notice_texts(
        _section(sections, "Operational Beta")
    ) == [UNAPPROVED_NOTICE]


@pytest.mark.parametrize(
    (
        "screening_complete",
        "applicable_ids",
        "approved_ids",
        "expected_state",
    ),
    [
        (
            False,
            set(),
            set(),
            (
                service.OPERATIONAL_SECTION_STATE_APPLICABILITY_UNKNOWN
            ),
        ),
        (
            True,
            set(),
            set(),
            service.OPERATIONAL_SECTION_STATE_NOT_APPLICABLE,
        ),
        (
            True,
            {"A.1"},
            set(),
            service.OPERATIONAL_SECTION_STATE_UNAPPROVED,
        ),
        (
            True,
            {"A.1", "A.2"},
            {"A.1"},
            (
                service.OPERATIONAL_SECTION_STATE_PARTIALLY_APPROVED
            ),
        ),
        (
            True,
            {"A.1", "A.2"},
            {"A.1", "A.2"},
            service.OPERATIONAL_SECTION_STATE_COMPLETE,
        ),
    ],
)
def test_operational_section_state_is_resolved_generically(
    screening_complete,
    applicable_ids,
    approved_ids,
    expected_state,
):
    assert (
        service._resolve_operational_section_state(
            screening_complete=screening_complete,
            applicable_ids=applicable_ids,
            approved_ids=approved_ids,
        )
        == expected_state
    )


def test_approved_content_without_configured_mapping_is_omitted():
    applicable = [
        _safety_point(
            "A.3.1",
            "alpha",
            "A.3",
        )
    ]

    sections = _build(
        screening_complete=True,
        applicable=applicable,
        approved=applicable,
    )

    assert [
        section.title
        for section in sections
    ] == [
        "Foundation",
        "Future Section",
    ]


def test_invalid_applicable_point_without_section_is_rejected():
    with pytest.raises(
        ValueError,
        match=(
            "applicable safety point is missing "
            "its source section ID"
        ),
    ):
        _build(
            screening_complete=True,
            applicable=[
                {
                    "safety_point_id": "A.1.1",
                    "safe_method_id": "A.1",
                }
            ],
        )
