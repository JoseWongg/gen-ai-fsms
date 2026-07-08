from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, TemplateError, meta


PROMPT_FILE = Path(__file__).with_name("safety_point_prompts.yaml")


class PromptRenderError(RuntimeError):
    pass


def _default(value: Any, fallback: str = "") -> Any:
    if value is None:
        return fallback

    return value


def _join_list(value: Any, separator: str = ", ") -> str:
    if not value:
        return ""

    if isinstance(value, (list, tuple, set)):
        return separator.join(str(item) for item in value if item)

    return str(value)


@lru_cache(maxsize=1)
def load_prompt_templates() -> dict[str, dict[str, str]]:
    with PROMPT_FILE.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    prompts = data.get("prompts")

    if not isinstance(prompts, dict):
        raise PromptRenderError("Prompt YAML must contain a 'prompts' mapping.")

    return prompts


@lru_cache(maxsize=1)
def get_jinja_environment() -> Environment:
    environment = Environment(
        autoescape=False,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )

    environment.filters["default_text"] = _default
    environment.filters["join_list"] = _join_list

    return environment


def render_prompt(prompt_key: str, context: dict[str, Any] | None = None) -> dict[str, str]:
    templates = load_prompt_templates()

    if prompt_key not in templates:
        raise PromptRenderError(f"Unknown prompt key: {prompt_key}")

    prompt_config = templates[prompt_key]

    if not isinstance(prompt_config, dict):
        raise PromptRenderError(f"Prompt '{prompt_key}' must be a mapping.")

    environment = get_jinja_environment()
    render_context = context or {}

    rendered: dict[str, str] = {}

    for role in ("system", "user"):
        template_text = prompt_config.get(role, "")

        if not isinstance(template_text, str):
            raise PromptRenderError(
                f"Prompt '{prompt_key}' field '{role}' must be a string."
            )

        try:
            parsed = environment.parse(template_text)
            missing_variables = meta.find_undeclared_variables(parsed) - set(
                render_context.keys()
            )

            safe_context = dict(render_context)
            for variable_name in missing_variables:
                safe_context[variable_name] = None

            rendered[role] = environment.from_string(template_text).render(
                **safe_context
            ).strip()

        except TemplateError as exc:
            raise PromptRenderError(
                f"Failed to render prompt '{prompt_key}' field '{role}'."
            ) from exc

    return rendered
