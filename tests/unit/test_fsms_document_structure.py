import json
from pathlib import Path


STRUCTURE_PATH = Path("data/fsms_document_structure.json")
SOURCE_CONTENT_PATH = Path("data/sfbb_chilling_cooking.json")

EXPECTED_SECTION_IDS = {
    "food_safety_policy",
    "business_and_hazard_overview",
    "temperature_control",
    "cooking_and_reheating",
    "cross_contamination_control",
    "cleaning_and_disinfection",
    "allergen_management",
    "pest_control",
    "deliveries_and_traceability",
    "training_responsibilities_and_review",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_source_safe_methods() -> dict[str, dict[str, str]]:
    source = load_json(SOURCE_CONTENT_PATH)
    result = {}

    for section in source["sections"]:
        for safe_method in section["safe_methods"]:
            result[safe_method["safe_method_id"]] = {
                "title": safe_method["safe_method_name"],
                "source_section_id": section["section_id"],
            }

    return result


def test_document_structure_has_expected_section_counts():
    structure = load_json(STRUCTURE_PATH)
    sections = structure["sections"]

    assert structure["planned_section_count"] == 10
    assert structure["supported_section_count"] == 4
    assert len(sections) == 10

    supported = [
        section
        for section in sections
        if section["implementation_status"] == "supported"
    ]
    beyond_scope = [
        section
        for section in sections
        if section["implementation_status"]
        == "beyond_prototype_scope"
    ]

    assert len(supported) == 4
    assert len(beyond_scope) == 6


def test_document_section_ids_and_orders_are_unique():
    sections = load_json(STRUCTURE_PATH)["sections"]

    section_ids = [section["section_id"] for section in sections]
    display_orders = [
        section["display_order"] for section in sections
    ]

    assert set(section_ids) == EXPECTED_SECTION_IDS
    assert len(section_ids) == len(set(section_ids))
    assert len(display_orders) == len(set(display_orders))
    assert sorted(display_orders) == list(range(1, 11))


def test_supported_sections_have_completion_rules():
    sections = load_json(STRUCTURE_PATH)["sections"]

    supported_sections = [
        section
        for section in sections
        if section["implementation_status"] == "supported"
    ]

    for section in supported_sections:
        assert section["completion_rule"]
        assert section["counts_towards_business_completion"] is True
        assert section["counts_towards_product_coverage"] is True


def test_beyond_scope_sections_do_not_count_towards_business_completion():
    sections = load_json(STRUCTURE_PATH)["sections"]

    beyond_scope_sections = [
        section
        for section in sections
        if section["implementation_status"]
        == "beyond_prototype_scope"
    ]

    for section in beyond_scope_sections:
        assert (
            section["counts_towards_business_completion"] is False
        )
        assert section["counts_towards_product_coverage"] is True


def test_safe_method_introductions_match_source_content():
    structure = load_json(STRUCTURE_PATH)
    introductions = structure["safe_method_introductions"]
    source_safe_methods = get_source_safe_methods()

    assert set(introductions) == set(source_safe_methods)
    assert len(introductions) == 10

    for safe_method_id, source_values in source_safe_methods.items():
        configured = introductions[safe_method_id]

        assert configured["title"] == source_values["title"]
        assert (
            configured["source_section_id"]
            == source_values["source_section_id"]
        )
        assert configured["introduction"].strip()


def test_supported_source_section_ids_exist_in_source_content():
    structure = load_json(STRUCTURE_PATH)
    source = load_json(SOURCE_CONTENT_PATH)
    source_section_ids = {
        section["section_id"]
        for section in source["sections"]
    }

    for section in structure["sections"]:
        for source_section_id in section["source_section_ids"]:
            assert source_section_id in source_section_ids


def test_appendices_do_not_affect_progress_counts():
    appendices = load_json(STRUCTURE_PATH)["appendices"]

    assert len(appendices) == 2

    for appendix in appendices:
        assert (
            appendix["counts_towards_business_completion"] is False
        )
        assert (
            appendix["counts_towards_product_coverage"] is False
        )



def test_document_structure_has_controlled_document_title():
    structure = load_json(STRUCTURE_PATH)

    assert structure["document_title"] == (
        "Food Safety Management System"
    )
