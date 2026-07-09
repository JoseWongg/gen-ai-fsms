import json
import logging
import re
from typing import Any, Optional

from gen_ai_fsms.ai.adapter import get_llm_adapter
from gen_ai_fsms.prompts.renderer import render_prompt

logger = logging.getLogger(__name__)

REVIEW_MESSAGE_FALLBACK = (
    "Please review this safety point. You can approve it, ask a question, "
    "or say if your business uses a different method."
)

APPROVAL_CONFIRMATION_FALLBACK = "Approval recorded for this safety point."

MAX_REVIEW_MESSAGE_CHARS = 500
MAX_CONFIRMATION_MESSAGE_CHARS = 300

ALLOWED_FACT_TYPES = {
    "business_activity",
    "food_type_or_ingredient",
    "equipment_used",
    "temperature_control_practice",
    "storage_practice",
    "cleaning_practice",
    "cooking_or_reheating_practice",
    "supplier_or_delivery_practice",
    "monitoring_or_recording_practice",
    "staff_training_practice",
    "other_business_operation",
}

FORBIDDEN_REVIEW_PATTERNS = (
    r"\bapproved\b",
    r"\bcompliant\b",
    r"\bcompliance\b",
    r"\bskip\b",
    r"\bnot required\b",
    r"\bdo not need to follow\b",
    r"\bdifferent method\b.*\b(safe|compliant|equivalent|acceptable)\b",
    r"\b(safe|compliant|equivalent|acceptable)\b.*\bdifferent method\b",
    r"food safety advis[eo]r",
)


def _normalise_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _extract_fact_texts(
    business_context: dict[str, Any],
    relevant_facts: Optional[list[Any]],
) -> list[str]:
    fact_source = relevant_facts
    if fact_source is None:
        fact_source = business_context.get("relevant_fact_texts")
    if fact_source is None:
        fact_source = business_context.get("relevant_facts", [])

    fact_texts: list[str] = []
    for fact in fact_source or []:
        if isinstance(fact, dict):
            fact_text = fact.get("fact_text")
        else:
            fact_text = str(fact)
        fact_text = _normalise_text(fact_text)
        if fact_text:
            fact_texts.append(fact_text)
    return fact_texts


def _contains_fixed_instruction(message: str, instruction: str) -> bool:
    clean_message = _normalise_text(message).lower()
    clean_instruction = _normalise_text(instruction).lower()

    if not clean_message or not clean_instruction:
        return False

    return clean_instruction in clean_message


def _has_forbidden_review_content(message: str) -> bool:
    clean_message = _normalise_text(message).lower()
    return any(
        re.search(pattern, clean_message)
        for pattern in FORBIDDEN_REVIEW_PATTERNS
    )


def _is_invalid_review_message(message: str, instruction: str) -> bool:
    clean_message = _normalise_text(message)

    if not clean_message:
        return True
    if len(clean_message) > MAX_REVIEW_MESSAGE_CHARS:
        return True
    if _contains_fixed_instruction(clean_message, instruction):
        return True
    if _has_forbidden_review_content(clean_message):
        return True

    return False


def _is_invalid_confirmation_message(message: str) -> bool:
    clean_message = _normalise_text(message).lower()

    if not clean_message:
        return True
    if len(clean_message) > MAX_CONFIRMATION_MESSAGE_CHARS:
        return True
    if "food safety adviser" in clean_message:
        return True
    if "food safety advisor" in clean_message:
        return True
    if "broader compliance" in clean_message:
        return True

    return False


def _normalise_facts_payload(payload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    facts = payload.get("facts", [])
    if not isinstance(facts, list):
        return {"facts": []}

    normalised_facts: list[dict[str, Any]] = []

    for fact in facts:
        if not isinstance(fact, dict):
            continue

        fact_type = _normalise_text(fact.get("fact_type"))
        fact_text = _normalise_text(fact.get("fact_text"))
        normalised_fact = _normalise_text(fact.get("normalised_fact"))

        if fact_type not in ALLOWED_FACT_TYPES:
            continue
        if not fact_text:
            continue

        raw_confidence = fact.get("confidence", 0.0)
        try:
            confidence = float(raw_confidence)
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(0.0, min(confidence, 1.0))

        normalised_facts.append(
            {
                "fact_type": fact_type,
                "fact_text": fact_text,
                "normalised_fact": normalised_fact,
                "confidence": confidence,
            }
        )

    return {"facts": normalised_facts}


class SafetyPointMessageComposer:
    """Compose LLM-assisted presentation text for safety point approval."""

    def __init__(self, llm_adapter: Any | None = None):
        self.llm_adapter = llm_adapter or get_llm_adapter()

    def _call_llm(
        self,
        rendered_prompt: dict[str, str],
        *,
        temperature: float,
        response_format: Optional[dict[str, str]] = None,
    ) -> Optional[str]:
        client = getattr(self.llm_adapter, "client", None)
        model = getattr(self.llm_adapter, "model", None)

        if not client or not model:
            return None

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": rendered_prompt["system"]},
                {"role": "user", "content": rendered_prompt["user"]},
            ],
            "temperature": temperature,
        }

        if response_format is not None:
            kwargs["response_format"] = response_format

        response = client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content.strip() if content else None

    def compose_safety_point_review_message(
        self,
        *,
        business_context: Optional[dict[str, Any]],
        safety_point: dict[str, Any],
        relevant_facts: Optional[list[Any]] = None,
    ) -> str:
        context = dict(business_context or {})
        instruction = _normalise_text(
            safety_point.get("instruction")
            or safety_point.get("safety_point_instruction")
            or safety_point.get("text")
            or safety_point.get("safety_point_text")
        )

        rendered_prompt = render_prompt(
            "safety_point_review_message",
            {
                "business_name": context.get("business_name"),
                "user_first_name": context.get("user_first_name"),
                "business_type_label": context.get("business_type_label"),
                "business_description": context.get("business_description"),
                "screening_activities": context.get("screening_activities", []),
                "relevant_facts": _extract_fact_texts(context, relevant_facts),
                "section_name": safety_point.get("section_name"),
                "safe_method_name": safety_point.get("safe_method_name"),
                "rationale": (
                    safety_point.get("rationale")
                    or safety_point.get("safety_point_rationale")
                    or ""
                ),
            },
        )

        try:
            message = self._call_llm(rendered_prompt, temperature=0.4)
        except Exception as exc:
            logger.error("LLM error in compose_safety_point_review_message: %s", exc)
            message = None

        if message is None:
            return REVIEW_MESSAGE_FALLBACK

        if _is_invalid_review_message(message, instruction):
            return REVIEW_MESSAGE_FALLBACK

        return _normalise_text(message)

    def compose_approval_confirmation(
        self,
        *,
        business_context: Optional[dict[str, Any]],
        safety_point: dict[str, Any],
        approved_count: Optional[int] = None,
        total_count: Optional[int] = None,
    ) -> str:
        context = dict(business_context or {})

        rendered_prompt = render_prompt(
            "approval_confirmation",
            {
                "business_name": context.get("business_name"),
                "user_first_name": context.get("user_first_name"),
                "section_name": safety_point.get("section_name"),
                "safe_method_name": safety_point.get("safe_method_name"),
                "approved_count": approved_count,
                "total_count": total_count,
            },
        )

        try:
            message = self._call_llm(rendered_prompt, temperature=0.3)
        except Exception as exc:
            logger.error("LLM error in compose_approval_confirmation: %s", exc)
            message = None

        if message is None:
            return APPROVAL_CONFIRMATION_FALLBACK

        if _is_invalid_confirmation_message(message):
            return APPROVAL_CONFIRMATION_FALLBACK

        return _normalise_text(message)

    def extract_business_context_facts(
        self,
        *,
        user_message: str,
        safety_point: dict[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        rendered_prompt = render_prompt(
            "fact_extraction",
            {
                "user_message": user_message,
                "safety_point_id": safety_point.get("safety_point_id"),
                "section_name": safety_point.get("section_name"),
                "safe_method_name": safety_point.get("safe_method_name"),
            },
        )

        try:
            content = self._call_llm(
                rendered_prompt,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as exc:
            logger.error("LLM error in extract_business_context_facts: %s", exc)
            content = None

        if not content:
            return {"facts": []}

        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return {"facts": []}

        if not isinstance(payload, dict):
            return {"facts": []}

        return _normalise_facts_payload(payload)
