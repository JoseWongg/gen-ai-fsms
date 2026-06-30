from decimal import Decimal, InvalidOperation
from typing import Any

FRIDGE_TYPE = "fridge"
FREEZER_TYPE = "freezer"

FRIDGE_MAX_COMPLIANT_TEMPERATURE = Decimal("8")
FREEZER_MAX_COMPLIANT_TEMPERATURE = Decimal("-18")


def normalize_chilling_equipment_type(equipment_type: str) -> str:
    if not equipment_type:
        raise ValueError("Equipment type is required.")

    normalized_type = equipment_type.strip().lower()

    fridge_values = {
        "fridge",
        "refrigerator",
        "chiller",
        "chilled",
    }

    freezer_values = {
        "freezer",
        "frozen",
    }

    if normalized_type in fridge_values:
        return FRIDGE_TYPE

    if normalized_type in freezer_values:
        return FREEZER_TYPE

    raise ValueError(f"Unsupported chilling equipment type: {equipment_type}")


def parse_temperature(temperature: Any) -> Decimal:
    try:
        return Decimal(str(temperature))
    except (InvalidOperation, TypeError):
        raise ValueError(f"Invalid temperature value: {temperature}") from None


def get_chilling_temperature_threshold(equipment_type: str) -> Decimal:
    normalized_type = normalize_chilling_equipment_type(equipment_type)

    if normalized_type == FRIDGE_TYPE:
        return FRIDGE_MAX_COMPLIANT_TEMPERATURE

    if normalized_type == FREEZER_TYPE:
        return FREEZER_MAX_COMPLIANT_TEMPERATURE

    raise ValueError(f"Unsupported chilling equipment type: {equipment_type}")


def is_chilling_temperature_compliant(
    equipment_type: str,
    temperature: Any,
) -> bool:
    parsed_temperature = parse_temperature(temperature)
    threshold = get_chilling_temperature_threshold(equipment_type)

    return parsed_temperature <= threshold


def build_chilling_temperature_non_compliance_message(
    equipment_name: str,
    equipment_type: str,
    temperature: Any,
    check_period: str,
) -> str:
    parsed_temperature = parse_temperature(temperature)
    threshold = get_chilling_temperature_threshold(equipment_type)
    normalized_type = normalize_chilling_equipment_type(equipment_type)

    return (
        f"Non-compliant {normalized_type} temperature recorded for "
        f"{equipment_name} during {check_period} check. "
        f"Recorded temperature: {parsed_temperature}°C. "
        f"Required threshold: must not exceed {threshold}°C."
    )