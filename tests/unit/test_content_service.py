# Add docstring to explain the purpose of this test module
"""Unit tests for the ContentService class in gen_ai_fsms.services.content_service.
These tests verify the loading of content, retrieval of safety points based on conditions,
and fetching of safety points by ID and their source references.

This will validate that:

    - JSON loads correctly.
    - Filtering respects inheritance (safety point 4.1.1.4 only appears if displays_chilled_food is true).
    - The enrichment (section_name, safe_method_name) works.
    - Source references are accessible.

To run these tests, use pytest in the terminal:
    pytest tests/unit/test_content_service.py
"""

import pytest
from gen_ai_fsms.services.content_service import ContentService

@pytest.fixture
def content_service():
    return ContentService()

def test_load_content(content_service):
    content = content_service.load_content()
    assert "sections" in content
    sections = content["sections"]
    assert len(sections) >= 2  # Chilling and Cooking
    section_ids = [s["section_id"] for s in sections]
    assert "chilling" in section_ids
    assert "cooking" in section_ids

def test_get_safety_points_by_conditions(content_service):
    # Test with conditions that should return safety points
    condition_values = {
        "chills_food": "true",
        "stores_or_displays_chilled_food": "true",
        "cooks_food": "true"
    }
    results = content_service.get_safety_points_by_conditions(condition_values)
    assert len(results) > 0
    # Check that each result has required fields
    for sp in results[:3]:
        assert "safety_point_id" in sp
        assert "text" in sp
        assert "safe_method_name" in sp
        assert "section_name" in sp

def test_filtering_inheritance(content_service):
    # Safety point 4.1.1.4 has its own condition "displays_chilled_food"
    # Without displays_chilled_food true, it should NOT appear
    condition_values_no_display = {
        "chills_food": "true",
        "stores_or_displays_chilled_food": "true",
        "displays_chilled_food": "false"
    }
    results_no_display = content_service.get_safety_points_by_conditions(condition_values_no_display)
    ids_no_display = [sp["safety_point_id"] for sp in results_no_display]
    assert "4.1.1.4" not in ids_no_display

    # With displays_chilled_food true, it should appear
    condition_values_display = {
        "chills_food": "true",
        "stores_or_displays_chilled_food": "true",
        "displays_chilled_food": "true"
    }
    results_display = content_service.get_safety_points_by_conditions(condition_values_display)
    ids_display = [sp["safety_point_id"] for sp in results_display]
    assert "4.1.1.4" in ids_display

def test_get_safety_point_by_id(content_service):
    sp = content_service.get_safety_point_by_id("4.1.1.1")
    assert sp is not None
    assert sp["safety_point_id"] == "4.1.1.1"
    assert "section_name" in sp
    assert "safe_method_name" in sp

def test_get_source_references(content_service):
    refs = content_service.get_source_references("4.1.1.3")
    assert len(refs) > 0
    assert "SFBB Pack > Chilling > Chilled Storage and Displaying Chilled Food" in refs[0]
