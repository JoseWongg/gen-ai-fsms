import json
from types import SimpleNamespace

import gen_ai_fsms.api.routes.onboarding_screening as screening_routes
from gen_ai_fsms.db.models.condition_value import (
    ConditionValue,
)
from gen_ai_fsms.services.screening_questions import (
    screening_questions,
)


class FakeAdapter:
    def __init__(self, result):
        self.result = result

    def interpret_screening_answer(
        self,
        question_text,
        answer,
        conversation,
    ):
        return dict(self.result)

    def suggest_screening_answer(
        self,
        *,
        business_description,
        question_text,
    ):
        return None


class FakeQuery:
    def filter_by(self, **kwargs):
        return self

    def first(self):
        return None


class FakeDb:
    def __init__(self):
        self.added = []
        self.commit_count = 0

    def query(self, model):
        assert model is ConditionValue
        return FakeQuery()

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commit_count += 1


def _screening_state(
    question,
    *,
    failed_answer_attempts=0,
):
    return {
        "screening_stage": "screening",
        "current_question_id": question["question_id"],
        "current_question_text": question["text"],
        "conditions_to_set": list(
            question.get("sets_conditions", [])
        ),
        "conversation_history": [],
        "display_messages": [],
        "answered_question_ids": [],
        "condition_values": {},
        "failed_answer_attempts": (
            failed_answer_attempts
        ),
        "clarification_attempts": 0,
        "unrelated_attempts": 0,
    }


def _profile():
    return SimpleNamespace(
        id=20,
        business_description="A test food business.",
        fsms_responsible_person_user_id=None,
        fsms_responsible_person_name=None,
    )


def test_records_full_name_snapshot():
    profile = _profile()
    current_user = SimpleNamespace(
        id=30,
        first_name="  Jose  Leonardo ",
        last_name=" Wong ",
    )

    screening_routes.record_fsms_responsible_person(
        profile,
        current_user,
    )

    assert (
        profile.fsms_responsible_person_user_id
        == 30
    )
    assert (
        profile.fsms_responsible_person_name
        == "Jose Leonardo Wong"
    )


def test_records_user_id_when_name_is_missing():
    profile = _profile()
    current_user = SimpleNamespace(
        id=31,
        first_name=" ",
        last_name=None,
    )

    screening_routes.record_fsms_responsible_person(
        profile,
        current_user,
    )

    assert (
        profile.fsms_responsible_person_user_id
        == 31
    )
    assert (
        profile.fsms_responsible_person_name
        is None
    )


def test_clear_final_answer_records_fsms_responsible_person(
    monkeypatch,
):
    question = screening_questions[0]
    profile = _profile()
    current_user = SimpleNamespace(
        id=32,
        first_name=" Jose ",
        last_name=" Wong ",
    )
    session = SimpleNamespace(
        id=10,
        state_json=json.dumps(
            _screening_state(question)
        ),
    )
    db = FakeDb()
    updates = []

    monkeypatch.setattr(
        screening_routes,
        "get_current_user_profile",
        lambda db, current_user: profile,
    )
    monkeypatch.setattr(
        screening_routes,
        "load_session",
        lambda db, business_profile_id, phase: (
            session
        ),
    )
    monkeypatch.setattr(
        screening_routes,
        "get_llm_adapter",
        lambda: FakeAdapter(
            {
                "action": "clear",
                "value": "true",
            }
        ),
    )
    monkeypatch.setattr(
        screening_routes,
        "get_next_question",
        lambda condition_values, answered_ids: None,
    )

    def fake_update_session(
        db,
        session_id,
        state_json,
        status="in_progress",
    ):
        updates.append(
            {
                "session_id": session_id,
                "status": status,
                "responsible_user_id": (
                    profile
                    .fsms_responsible_person_user_id
                ),
                "responsible_name": (
                    profile
                    .fsms_responsible_person_name
                ),
            }
        )
        return session

    monkeypatch.setattr(
        screening_routes,
        "update_session",
        fake_update_session,
    )

    result = screening_routes.submit_answer(
        screening_routes.AnswerRequest(
            answer="Yes"
        ),
        db=db,
        current_user=current_user,
    )

    assert result["action"] == "complete"
    assert (
        profile.fsms_responsible_person_user_id
        == 32
    )
    assert (
        profile.fsms_responsible_person_name
        == "Jose Wong"
    )
    assert updates == [
        {
            "session_id": 10,
            "status": "completed",
            "responsible_user_id": 32,
            "responsible_name": "Jose Wong",
        }
    ]


def test_unresolved_unknown_does_not_record_responsible_person(
    monkeypatch,
):
    question = screening_questions[0]
    profile = _profile()
    current_user = SimpleNamespace(
        id=33,
        first_name=" Jose ",
        last_name=" Wong ",
    )
    session = SimpleNamespace(
        id=11,
        state_json=json.dumps(
            _screening_state(
                question,
                failed_answer_attempts=2,
            )
        ),
    )
    db = FakeDb()
    updates = []

    monkeypatch.setattr(
        screening_routes,
        "get_current_user_profile",
        lambda db, current_user: profile,
    )
    monkeypatch.setattr(
        screening_routes,
        "load_session",
        lambda db, business_profile_id, phase: (
            session
        ),
    )
    monkeypatch.setattr(
        screening_routes,
        "get_llm_adapter",
        lambda: FakeAdapter(
            {
                "action": "ambiguous",
                "value": None,
            }
        ),
    )
    monkeypatch.setattr(
        screening_routes,
        "get_next_question",
        lambda condition_values, answered_ids: None,
    )

    def fake_update_session(
        db,
        session_id,
        state_json,
        status="in_progress",
    ):
        updates.append(status)
        return session

    monkeypatch.setattr(
        screening_routes,
        "update_session",
        fake_update_session,
    )

    result = screening_routes.submit_answer(
        screening_routes.AnswerRequest(
            answer="I am not sure"
        ),
        db=db,
        current_user=current_user,
    )

    assert result["action"] == "next_question"
    assert updates == ["in_progress"]
    assert (
        profile.fsms_responsible_person_user_id
        is None
    )
    assert (
        profile.fsms_responsible_person_name
        is None
    )


def test_ambiguous_completion_fallback_does_not_record_responsible_person(
    monkeypatch,
):
    question = screening_questions[0]
    state = _screening_state(
        question,
        failed_answer_attempts=2,
    )
    state["conditions_to_set"] = []

    profile = _profile()
    current_user = SimpleNamespace(
        id=34,
        first_name=" Jose ",
        last_name=" Wong ",
    )
    session = SimpleNamespace(
        id=12,
        state_json=json.dumps(state),
    )
    db = FakeDb()
    updates = []

    monkeypatch.setattr(
        screening_routes,
        "get_current_user_profile",
        lambda db, current_user: profile,
    )
    monkeypatch.setattr(
        screening_routes,
        "load_session",
        lambda db, business_profile_id, phase: (
            session
        ),
    )
    monkeypatch.setattr(
        screening_routes,
        "get_llm_adapter",
        lambda: FakeAdapter(
            {
                "action": "ambiguous",
                "value": None,
            }
        ),
    )
    monkeypatch.setattr(
        screening_routes,
        "get_next_question",
        lambda condition_values, answered_ids: None,
    )

    def fake_update_session(
        db,
        session_id,
        state_json,
        status="in_progress",
    ):
        updates.append(status)
        return session

    monkeypatch.setattr(
        screening_routes,
        "update_session",
        fake_update_session,
    )

    result = screening_routes.submit_answer(
        screening_routes.AnswerRequest(
            answer="I cannot answer this"
        ),
        db=db,
        current_user=current_user,
    )

    assert result["action"] == "complete"
    assert updates == ["completed"]
    assert (
        profile.fsms_responsible_person_user_id
        is None
    )
    assert (
        profile.fsms_responsible_person_name
        is None
    )
