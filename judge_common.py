"""Backend-agnostic pieces of the judging pipeline.

Every backend module (`judge.py`, `judge_deepseek.py`, `judge_gemini.py`,
`judge_ollama.py`) imports from here so the system prompt, decision shape,
and tool schema stay in sync.

A backend module needs to expose `judge(frames: list[bytes]) -> Decision`.
"""

import re
from dataclasses import dataclass, field
from typing import Any

import httpx

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


def decision_from_tool_args(args: dict, usage: dict) -> Decision:
    """Build a Decision from a tool-call argument dict, tolerating mild
    schema drift (non-Anthropic backends miss keys more often than Claude).

    Shared by the OpenAI-compatible backends (Ollama, DeepSeek) so a field
    default or a clamp rule only has to be right once. Missing fields fall
    back to safe defaults; enum-like fields are clamped to allowed values so
    a stray value can't break the loop.

    Note the defaults must stay in sync with the Decision fields above —
    passing a key that isn't on the dataclass raises TypeError.
    """
    defaults = {
        "name": "unknown",
        "decision": "skip",
        "confidence": "low",
        "reasoning": "",
        "skip_reason": "other",
    }
    merged = {**defaults, **{k: v for k, v in args.items() if k in defaults}}
    # Clamp enum-like fields to allowed values
    if merged["decision"] not in ("like", "skip"):
        merged["decision"] = "skip"
    if merged["confidence"] not in ("low", "medium", "high"):
        merged["confidence"] = "low"
    return Decision(**merged, usage=usage)


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


# ── Fatal judge errors ────────────────────────────────────────────────
# Errors that will NOT clear on a retry. Retrying them burns Bumble swipes
# blind: a judge that fails all three attempts falls through to a
# force-skip, so a dead API key or an empty balance silently skips every
# profile in the feed until the daily quota is gone. (Seen once on the Hinge
# sibling repo when the Anthropic credit balance hit zero mid-run — 124
# profiles were skipped before anyone noticed.)
#
# Classify by HTTP status where one exists; that's the only
# backend-independent signal. Providers word the same failure differently
# (Anthropic: "credit balance is too low", DeepSeek: "Insufficient
# Balance"), so message text is a fallback, not the primary key.
FATAL_STATUS_CODES = frozenset({
    400,  # malformed request / unsupported parameter — a config bug, not a blip
    401,  # bad or missing API key
    402,  # payment required — DeepSeek's "Insufficient Balance"
    403,  # key is valid but not permitted for this call
    404,  # model not found
    422,  # unprocessable request — also a request-shape bug
})

# Catches backends that only put the code in the text, e.g.
# judge_deepseek.py's RuntimeError("DeepSeek API error 402: {...}").
_STATUS_IN_TEXT = re.compile(r"(?:API|HTTP|status)\D{0,10}(\d{3})\b", re.IGNORECASE)

# Last resort, for errors carrying neither a status attribute nor a
# parseable one in the message.
_FATAL_PHRASES = (
    "credit balance is too low",
    "insufficient balance",
    "insufficient_quota",
    "authentication_error",
    "invalid_api_key",
    "permission_error",
    "invalid_request_error",
    "model not found",
    # Shared tail of the "<NAME>_API_KEY not set. Add it to .env or export
    # it." guard in the backend modules. A missing key never clears on
    # retry, and without this the loop spends all three attempts failing
    # before blindly skipping every profile in the feed.
    "not set. add it to .env",
)


def _http_status(exc: BaseException) -> int | None:
    """Best-effort HTTP status for an exception from any backend."""
    for attr in ("status_code", "status", "http_status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
    # requests/httpx style: HTTPStatusError carries .response.status_code
    val = getattr(getattr(exc, "response", None), "status_code", None)
    return val if isinstance(val, int) else None


def is_fatal_judge_error(exc: BaseException) -> bool:
    """True if `exc` won't clear on retry, so the run should halt.

    Walks the exception chain, because backends and vendor SDKs wrap the
    interesting error (`raise X from e`) and the status usually sits on an
    inner link rather than the one the caller catches.
    """
    seen = set()
    cur = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))

        status = _http_status(cur)
        if status is not None and status in FATAL_STATUS_CODES:
            return True

        text = str(cur)
        for match in _STATUS_IN_TEXT.finditer(text):
            if int(match.group(1)) in FATAL_STATUS_CODES:
                return True

        lowered = text.lower()
        if any(phrase in lowered for phrase in _FATAL_PHRASES):
            return True

        cur = cur.__cause__ or cur.__context__
    return False


# httpx is the transport under every backend — the Anthropic and OpenAI SDKs
# both sit on it, google-genai does too, and judge_deepseek.py calls it
# directly — so a transport-level failure surfaces as the same family of
# exceptions whichever judge is configured.
#
# The names cover errors an SDK wrapper raises instead of passing the httpx
# one through: Anthropic's APIConnectionError subclasses APIError, not
# httpx.TransportError, so isinstance alone would miss it. gaierror is DNS
# failure, the usual shape of "the internet cut out" underneath httpx's
# own wrapping.
_NETWORK_ERROR_NAMES = frozenset({
    "ConnectError", "ConnectTimeout", "ReadError", "ReadTimeout",
    "WriteError", "WriteTimeout", "PoolTimeout", "RemoteProtocolError",
    "APIConnectionError", "APITimeoutError", "gaierror",
})


def is_network_error(exc: BaseException) -> bool:
    """True if `exc` means the request never reached the model.

    These are deliberately absent from FATAL_STATUS_CODES: a dropped packet
    is retryable in principle, so one shouldn't abort a run. But when they
    outlast every retry the network is down, and the caller has to end the
    run — force-skipping would spend real Bumble profiles on people the
    judge never scored. Walks the exception chain the way
    is_fatal_judge_error does, so wrapper layers don't hide the cause.
    """
    seen = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, httpx.TransportError):
            return True
        if _NETWORK_ERROR_NAMES & {c.__name__ for c in type(cur).__mro__}:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


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
    if backend == "deepseek":
        import judge_deepseek
        return judge_deepseek
    raise ValueError(
        f"Unknown JUDGE_BACKEND={backend!r}. Use 'anthropic', 'deepseek', "
        f"'gemini', or 'ollama'."
    )
