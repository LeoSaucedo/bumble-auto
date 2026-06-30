"""Backend-agnostic pieces of the judging pipeline.

Both `judge.py` (Anthropic) and `judge_ollama.py` (Ollama) import from
here so the system prompt, decision shape, and tool schema stay in sync.

A backend module needs to expose `judge(frames: list[bytes]) -> Decision`.
"""

from dataclasses import dataclass, field
from typing import Any

import config


SYSTEM_PROMPT_TEMPLATE = """You are evaluating Bumble dating profiles on behalf of the user.

The user's preferences:
{preferences}
{age_clause}
You will be shown a sequence of screenshots representing a single profile, in
order from top to bottom. The profile may include photos, prompt responses
(short text), and basic info (age, height, location, job, education, etc.).

Decide SWIPE RIGHT or SWIPE LEFT based on the user's preferences. Be generous
with right-swipes — the bar should be "would I potentially go on a date with
this person?" not "is this my dream partner?" When genuinely on the fence, lean
SWIPE RIGHT.

{volume_guidance}
Submit your decision via the submit_decision tool."""


DEFAULT_VOLUME_GUIDANCE = """## Swipe volume

Aim to swipe right on roughly half the profiles you see. If you've been
swiping left a lot, loosen up. If you've been swiping right on every profile,
be more selective. The goal is volume with some quality filtering — not
perfectionism."""


# JSON schema for the submit_decision tool.
DECIDE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "description": (
                "The profile's first name as shown at the top of the "
                "profile. Lowercase, ASCII letters only — strip "
                "spaces, punctuation, emoji. If not visible, use "
                "\"unknown\"."
            ),
        },
        "decision": {
            "type": "string",
            "enum": ["like", "skip"],
            "description": "SWIPE RIGHT ('like') or SWIPE LEFT ('skip').",
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How confident you are in the decision.",
        },
        "reasoning": {
            "type": "string",
            "description": (
                "One sentence explaining the decision. Reference "
                "specific details from the profile."
            ),
        },
        "skip_reason": {
            "type": "string",
            "enum": ["none", "age", "preferences", "low_effort", "other"],
            "description": (
                "Categorical skip reason. \"none\" when decision == \"like\". "
                "\"age\" when AGE GATE triggered. "
                "\"preferences\" when a PREFERENCES rule fired. "
                "\"low_effort\" when the profile is too thin to evaluate. "
                "\"other\" only if nothing else fits."
            ),
        },
    },
    "required": [
        "name", "decision", "confidence", "reasoning", "skip_reason",
    ],
}


@dataclass
class Decision:
    name: str
    decision: str  # "like" | "skip"
    confidence: str  # "low" | "medium" | "high"
    reasoning: str
    skip_reason: str = "none"
    usage: dict[str, Any] = field(default_factory=dict)


def _age_clause(age_min: int | None, age_max: int | None) -> str:
    if age_min is None and age_max is None:
        return ""
    lo = age_min if age_min is not None else 18
    hi = age_max if age_max is not None else 99
    return (
        f"\nAGE GATE: only SWIPE RIGHT if the profile's stated age is "
        f"between {lo} and {hi} inclusive. If age is visible and out of "
        f"range, decision=skip, skip_reason=\"age\". If age genuinely "
        f"isn't visible across any frame, proceed with the normal rubric.\n"
    )


def build_system_prompt() -> str:
    volume = getattr(config, "SWIPE_VOLUME_GUIDANCE", None)
    if volume is None:
        volume = DEFAULT_VOLUME_GUIDANCE
    return SYSTEM_PROMPT_TEMPLATE.format(
        preferences=config.PREFERENCES.strip(),
        age_clause=_age_clause(config.AGE_MIN, config.AGE_MAX),
        volume_guidance=volume.strip(),
    )


def load_backend():
    """Resolve config.JUDGE_BACKEND to a module exposing judge(frames)."""
    backend = getattr(config, "JUDGE_BACKEND", "anthropic").lower()
    if backend == "anthropic":
        import judge
        return judge
    if backend == "ollama":
        import judge_ollama
        return judge_ollama
    if backend == "gemini":
        import judge_gemini
        return judge_gemini
    raise ValueError(
        f"Unknown JUDGE_BACKEND={backend!r}. Use 'anthropic', 'ollama', or 'gemini'."
    )
