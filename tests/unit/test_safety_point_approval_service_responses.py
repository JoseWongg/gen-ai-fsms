import pytest

from gen_ai_fsms.db.models.approved_safety_point_response import (
    ApprovedSafetyPointResponse,
)
from gen_ai_fsms.services.safety_point_approval_service import (
    record_approved_safety_point,
)


class FakeSession:
    def __init__(self):
        self.added_records = []

    def add(self, record):
        self.added_records.append(record)

    def flush(self):
        for record in self.added_records:
            if (
                record.__class__.__name__ == "ApprovedSafetyPoint"
                and record.id is None
            ):
                record.id = 101


def _safety_point():
    return {
        "safety_point_id": "5.5.1.1",
        "safe_method_id": "5.5",
        "safe_method_name": "Hot Holding",
        "text": "Use suitable equipment to keep hot food hot.",
        "additional_questions": [
            {
                "question_key": "hot_holding_equipment",
                "question_text": (
                    "What equipment does the business use for hot holding?"
                ),
            }
        ],
    }


def test_record_approval_stores_raw_and_document_responses():
    db = FakeSession()

    result = record_approved_safety_point(
        db=db,
        business_profile_id=1,
        user_id=10,
        safety_point=_safety_point(),
        additional_answers={
            "hot_holding_equipment": (
                "We normally use the bain-marie, but there is also a "
                "heated display unit for busy services."
            )
        },
        document_additional_answers={
            "hot_holding_equipment": (
                "A bain-marie and a heated display unit are used during busy services for hot holding."
            )
        },
    )

    responses = [
        record
        for record in db.added_records
        if isinstance(record, ApprovedSafetyPointResponse)
    ]

    assert result["additional_response_count"] == 1
    assert len(responses) == 1

    response = responses[0]

    assert response.response_text == (
        "We normally use the bain-marie, but there is also a "
        "heated display unit for busy services."
    )
    assert response.document_response_text == (
        "A bain-marie and a heated display unit are used during busy services for hot holding."
    )


def test_record_approval_rejects_missing_document_response():
    db = FakeSession()

    with pytest.raises(
        ValueError,
        match=(
            "Missing document response text for additional question "
            "'hot_holding_equipment'"
        ),
    ):
        record_approved_safety_point(
            db=db,
            business_profile_id=1,
            user_id=10,
            safety_point=_safety_point(),
            additional_answers={
                "hot_holding_equipment": "We use a bain-marie."
            },
            document_additional_answers={},
        )
