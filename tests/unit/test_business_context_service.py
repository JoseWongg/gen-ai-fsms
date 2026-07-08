import json
from types import SimpleNamespace

import pytest

from gen_ai_fsms.services import business_context_service
from gen_ai_fsms.services.business_context_service import (
    get_business_context,
    get_business_type_label,
    get_screening_activities,
    normalise_text,
)


class FakeQuery:
    def __init__(self, first_result=None, all_result=None):
        self.first_result = first_result
        self.all_result = all_result or []

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self.first_result

    def all(self):
        return self.all_result


class FakeSession:
    def __init__(self, query_results):
        self.query_results = query_results
        self.query_count = 0
        self.add_called = False
        self.commit_called = False
        self.flush_called = False
        self.delete_called = False

    def query(self, model):
        result = self.query_results[self.query_count]
        self.query_count += 1
        return result

    def add(self, *args, **kwargs):
        self.add_called = True

    def commit(self, *args, **kwargs):
        self.commit_called = True

    def flush(self, *args, **kwargs):
        self.flush_called = True

    def delete(self, *args, **kwargs):
        self.delete_called = True


def test_normalise_text_collapses_whitespace_and_handles_none():
    assert normalise_text(None) == ""
    assert normalise_text("  Cakes   and   cupcakes  ") == "Cakes and cupcakes"


def test_get_business_type_label_uses_known_labels_and_fallbacks():
    assert get_business_type_label("bakery") == "Bakery"
    assert get_business_type_label("sandwich_shop") == "Sandwich shop"
    assert get_business_type_label("custom_food_business") == "Custom Food Business"
    assert get_business_type_label(None) == ""


def test_get_screening_activities_returns_true_condition_labels_only():
    activities = get_screening_activities(
        {
            "chills_food": "true",
            "cooks_food": "true",
            "handles_eggs": "false",
            "custom_condition": "true",
        }
    )

    assert "uses chilled storage" in activities
    assert "prepares or cooks food on site" in activities
    assert "uses eggs or foods containing eggs" not in activities
    assert "custom condition" in activities


def test_get_business_context_returns_json_serialisable_context(monkeypatch):
    business_profile = SimpleNamespace(
        id=1,
        business_name=" Nathan's Cakes ",
        site_name=" Main Kitchen ",
        business_type="bakery",
        business_description="  Makes celebration cakes   and cupcakes. ",
    )
    user = SimpleNamespace(
        id=10,
        first_name=" Nathan ",
        business_profile_id=1,
    )
    condition_rows = [
        SimpleNamespace(condition_id="chills_food", value="true"),
        SimpleNamespace(condition_id="cooks_food", value="true"),
        SimpleNamespace(condition_id="handles_eggs", value="false"),
    ]
    facts = [
        SimpleNamespace(
            fact_type="monitoring_or_recording_practice",
            fact_text="The business checks fridge temperatures every day.",
            normalised_fact="checks_fridge_temperatures_daily",
            confidence=0.95,
        )
    ]

    monkeypatch.setattr(
        business_context_service,
        "list_business_context_facts_for_profile",
        lambda **kwargs: facts,
    )

    db = FakeSession(
        [
            FakeQuery(first_result=business_profile),
            FakeQuery(first_result=user),
            FakeQuery(all_result=condition_rows),
        ]
    )

    context = get_business_context(
        db=db,
        business_profile_id=1,
        user_id=10,
        relevant_fact_types={"monitoring_or_recording_practice"},
    )

    assert context["user_first_name"] == "Nathan"
    assert context["business_name"] == "Nathan's Cakes"
    assert context["site_name"] == "Main Kitchen"
    assert context["business_type"] == "bakery"
    assert context["business_type_label"] == "Bakery"
    assert context["business_description"] == (
        "Makes celebration cakes and cupcakes."
    )
    assert context["condition_values"] == {
        "chills_food": "true",
        "cooks_food": "true",
        "handles_eggs": "false",
    }
    assert "uses chilled storage" in context["screening_activities"]
    assert "prepares or cooks food on site" in context["screening_activities"]
    assert context["relevant_facts"] == [
        {
            "fact_type": "monitoring_or_recording_practice",
            "fact_text": "The business checks fridge temperatures every day.",
            "normalised_fact": "checks_fridge_temperatures_daily",
            "confidence": 0.95,
        }
    ]
    assert context["relevant_fact_texts"] == [
        "The business checks fridge temperatures every day."
    ]

    json.dumps(context)

    assert db.add_called is False
    assert db.commit_called is False
    assert db.flush_called is False
    assert db.delete_called is False


def test_get_business_context_handles_missing_optional_user(monkeypatch):
    business_profile = SimpleNamespace(
        id=1,
        business_name="Legacy Business",
        site_name=None,
        business_type=None,
        business_description=None,
    )

    monkeypatch.setattr(
        business_context_service,
        "list_business_context_facts_for_profile",
        lambda **kwargs: [],
    )

    db = FakeSession(
        [
            FakeQuery(first_result=business_profile),
            FakeQuery(all_result=[]),
        ]
    )

    context = get_business_context(
        db=db,
        business_profile_id=1,
        user_id=None,
    )

    assert context["user_first_name"] == ""
    assert context["business_name"] == "Legacy Business"
    assert context["site_name"] == ""
    assert context["business_type"] == ""
    assert context["business_type_label"] == ""
    assert context["business_description"] == ""
    assert context["screening_activities"] == []
    assert context["relevant_facts"] == []


def test_get_business_context_rejects_missing_business_profile():
    db = FakeSession([FakeQuery(first_result=None)])

    with pytest.raises(ValueError, match="Business profile not found"):
        get_business_context(db=db, business_profile_id=999)
