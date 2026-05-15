"""
Hard‑coded screening questions for the SFBB onboarding flow.
Each question sets one or more condition values.
The flow is deterministic: next question is chosen by order and dependency logic.
"""

screening_questions = [
    # Stage 1 – Broad operational questions
    {
        "question_id": "q_chills_food", # Note: chills_food means keeping food chilled/cold, not cooling hot food down.
        "text": "Do you keep any food chilled in fridges or chilled display units?",
        "sets_conditions": ["chills_food"],
        "ask_if": None,
        "order": 1
    },
    {
        "question_id": "q_chills_hot_food",
        "text": "Do you cool hot cooked food for later use or storage?",
        "sets_conditions": ["chills_hot_food"],
        "ask_if": None,
        "order": 2
    },
    {
        "question_id": "q_defrosts_food",
        "text": "Do you defrost frozen food before use?",
        "sets_conditions": ["defrosts_food"],
        "ask_if": None,
        "order": 3
    },
    {
        "question_id": "q_freezes_food",
        "text": "Do you freeze food on site or store food in freezers?",
        "sets_conditions": ["freezes_food"],
        "ask_if": None,
        "order": 4
    },
    {
        "question_id": "q_cooks_food", # Note: It includes food preparation, not just cooking with heat.
        "text": "Do you prepare or cook food on site?",
        "sets_conditions": ["cooks_food"],
        "ask_if": None,
        "order": 5
    },
    {
        "question_id": "q_reheats_food",
        "text": "Do you reheat previously cooked food?",
        "sets_conditions": ["reheats_food"],
        "ask_if": None,
        "order": 6
    },
    {
        "question_id": "q_hot_holds_food",
        "text": "Do you keep food hot before serving?",
        "sets_conditions": ["hot_holds_food"],
        "ask_if": None,
        "order": 7
    },
    {
        "question_id": "q_handles_ready_to_eat_food",
        "text": "Do you prepare ready-to-eat food such as salads, sandwiches, desserts, or cooked foods served cold?",
        "sets_conditions": ["handles_ready_to_eat_food"],
        "ask_if": None,
        "order": 8
    },
    {
        "question_id": "q_delivers_food",
        "text": "Do you deliver food to customers or prepare food for collection?",
        "sets_conditions": ["delivers_food"],
        "ask_if": None,
        "order": 9
    },

    # Stage 2 – Narrower refinement questions (only if parent condition true)
    {
        "question_id": "q_handles_raw_meat_or_poultry",
        "text": "Do you handle raw meat or poultry?",
        "sets_conditions": ["handles_raw_meat_or_poultry"],
        "ask_if": {"cooks_food": "true"},
        "order": 10
    },
    {
        "question_id": "q_cooks_rice",
        "text": "Do you cook rice?",
        "sets_conditions": ["cooks_rice"],
        "ask_if": {"cooks_food": "true"},
        "order": 11
    },
    {
        "question_id": "q_handles_eggs",
        "text": "Do you use eggs or make foods containing eggs?",
        "sets_conditions": ["handles_eggs"],
        "ask_if": {"cooks_food": "true"},
        "order": 12
    },
    {
        "question_id": "q_cooks_dried_pulses",
        "text": "Do you cook dried pulses such as dried beans?",
        "sets_conditions": ["cooks_dried_pulses"],
        "ask_if": {"cooks_food": "true"},
        "order": 13
    },
    {
        "question_id": "q_handles_raw_fish",
        "text": "Do you cook or handle fish?",
        "sets_conditions": ["handles_raw_fish"],
        "ask_if": {"cooks_food": "true"},
        "order": 14
    },
    {
        "question_id": "q_handles_raw_molluscs_or_crustaceans",
        "text": "Do you cook or handle shellfish such as prawns, mussels, scallops, crab, or lobster?",
        "sets_conditions": ["handles_raw_molluscs_or_crustaceans"],
        "ask_if": {"cooks_food": "true"},
        "order": 15
    },
    {
        "question_id": "q_handles_bread_bakery_or_potatoes",
        "text": "Do you cook bread, bakery products, chips, fries, or similar potato products, or handle them for service or sale?",
        "sets_conditions": ["handles_bread_bakery_or_potatoes"],
        "ask_if": {"cooks_food": "true"},
        "order": 16
    },
    {
        "question_id": "q_uses_sink_to_defrost_food",
        "text": "Do you use a sink to defrost food?",
        "sets_conditions": ["uses_sink_to_defrost_food"],
        "ask_if": {"defrosts_food": "true"},
        "order": 17
    },
    {
        "question_id": "q_buys_frozen_food",
        "text": "Do you buy food that arrives frozen?",
        "sets_conditions": ["buys_frozen_food"],
        "ask_if": {"freezes_food": "true"},
        "order": 18
    },
    {
        "question_id": "q_stores_food_that_must_be_kept_frozen",
        "text": "Do you store food that must remain frozen, such as ice cream?",
        "sets_conditions": ["stores_food_that_must_be_kept_frozen"],
        "ask_if": {"freezes_food": "true"},
        "order": 19
    },
    {
        "question_id": "q_uses_microwave_reheating",
        "text": "Do you use a microwave to reheat food?",
        "sets_conditions": ["uses_microwave_reheating"],
        "ask_if": {"reheats_food": "true"},
        "order": 20
    },
    {
        "question_id": "q_displays_hot_food",
        "text": "Do you display hot food, for example on a buffet or service counter?",
        "sets_conditions": ["displays_hot_food"],
        "ask_if": {"hot_holds_food": "true"},
        "order": 21
    },
    {
        "question_id": "q_uses_slicer",
        "text": "Do you use a slicer for cooked meat or ready-to-eat food?",
        "sets_conditions": ["uses_slicer"],
        "ask_if": {"handles_ready_to_eat_food": "true"},
        "order": 22
    },
    {
        "question_id": "q_displays_chilled_food",
        "text": "Do you display chilled food for customers, buffet service, or self‑service?",
        "sets_conditions": ["displays_chilled_food"],
        "ask_if": {"chills_food": "true"},
        "order": 24
    }
]

def get_questions_for_condition_values(condition_values: dict) -> list:
    """
    Return the list of questions that should be asked given the current condition values.
    Filters by ask_if condition (if present). Does NOT filter already answered questions.
    Order is preserved.
    """
    result = []
    for q in screening_questions:
        ask_if = q.get("ask_if")
        if ask_if is not None:
            # All conditions in ask_if must be true to ask this question
            if all(condition_values.get(k) == "true" for k in ask_if):
                result.append(q)
        else:
            result.append(q)
    return result

def get_next_question(condition_values: dict, already_answered_ids: set) -> dict | None:
    """
    Deterministic next question: the first unanswered question whose ask_if conditions are met.
    """
    for q in get_questions_for_condition_values(condition_values):
        if q["question_id"] not in already_answered_ids:
            return q
    return None
