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
(short text), and basic info (age, height, job, education, etc.).
{location_clause}
{fit_clause}
DIALOGS: the screenshots are captured one after another as the profile is
scrolled, so a dialog, popup, overlay or other non-profile screen often
appears partway through — a rating nag, upsell, notification prompt or
settings panel that covers the screen from some frame onward while the
earlier frames are still clean. A dialog covering the screen in ANY frame
means decision="NOT_A_PROFILE", even when the first frame or two show a real
profile. Do not score the clean frames and disregard the covered ones, and do
not assume the covered frames are just more of the same profile — describe
the dialog in reasoning instead.

{volume_guidance}
Submit your decision via the submit_decision tool."""


DEFAULT_VOLUME_GUIDANCE = """## Scoring calibration

Score honestly and use the full range — don't cluster everything around the
middle. The harness applies the like threshold to your fit_score, so your job
is an accurate score, not a target number of likes. Don't inflate scores to
be agreeable and don't deflate them to seem selective: a profile that matches
the rubric well should score high even if you've liked a lot already, and one
that misses should score low even if you've liked nothing."""


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
            "enum": ["profile", "NOT_A_PROFILE"],
            "description": (
                "'profile' when the screenshots show a real profile you can "
                "score. 'NOT_A_PROFILE' when a dialog, popup, overlay, or "
                "non-profile screen blocks full analysis (use reasoning to "
                "describe it). Do NOT choose like vs skip — the harness "
                "decides that from fit_score."
            ),
        },
        "fit_score": {
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
            "description": (
                "How well this profile fits the user's preferences, 0-100. "
                "Use the full range: 90+ = exact match, 75-89 = strong fit, "
                "60-74 = decent, 40-59 = neutral, 0-39 = not a fit. This is "
                "the authoritative score the run uses to decide like vs skip."
            ),
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
            "description": "How confident you are in the fit_score.",
        },
        "reasoning": {
            "type": "string",
            "description": (
                "One or two sentences explaining the score. Reference "
                "specific details from the profile (e.g., a prompt answer, "
                "an activity in a photo, the bio/info line)."
            ),
        },
        "dominant_factor": {
            "type": "string",
            "enum": [
                "none",
                "other",
                "age",
                "looks",
                "build",
                "photos",
                "height",
                "religion",
                "low_effort",
                "grooming",
                "tattoos",
                "ethnicity",
                "lifestyle",
                "interests",
                "humor",
                "frame",
                "style",
            ],
            "description": (
                "Which single factor from the PREFERENCES rubric most drove "
                "this fit_score, for downstream analytics. Report it in BOTH "
                "directions — a factor that pulled the score UP is as worth "
                "recording as one that pulled it down; fit_score says which "
                "way it cut. \"age\" when the AGE GATE fired, \"low_effort\" "
                "when the profile was too thin to engage with (no readable "
                "prompts, single photo, etc.). Use \"none\" only when no "
                "single factor dominated and the score came from the overall "
                "read of the profile, and \"other\" only if nothing above "
                "fits. Name the factor even when it argues for a like."
            ),
        },
    },
    "required": [
        "name", "decision", "fit_score", "confidence", "reasoning",
        "dominant_factor",
    ],
}


@dataclass
class Decision:
    name: str
    # Model's verdict: "profile" | "NOT_A_PROFILE". After apply_fit_threshold
    # it becomes the run's verdict: "like" | "skip" | "NOT_A_PROFILE".
    decision: str
    confidence: str  # "low" | "medium" | "high"
    reasoning: str
    fit_score: int = 0  # 0-100, authoritative for like/skip gating
    dominant_factor: str = "none"
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
        # Missing/odd verdicts are treated as a scoreable profile — the
        # fit-score gate downstream is what decides like vs skip.
        "decision": "profile",
        "fit_score": 0,
        "confidence": "low",
        "reasoning": "",
        "dominant_factor": "other",
    }
    merged = {**defaults, **{k: v for k, v in args.items() if k in defaults}}
    # Clamp the model's profile/NOT_A_PROFILE verdict — NOT_A_PROFILE must
    # survive so main.py's dialog recovery still fires. Anything else
    # (including a stray like/skip) is treated as a scoreable profile;
    # like vs skip is decided downstream by apply_fit_threshold.
    if merged["decision"] != "NOT_A_PROFILE":
        merged["decision"] = "profile"
    if merged["confidence"] not in ("low", "medium", "high"):
        merged["confidence"] = "low"
    return Decision(**merged, usage=usage)


def _fit_clause() -> str:
    return (
        f"\nFIT SCORE: one integer fit_score (0-100) for how well this profile "
        f"matches the user's preferences. Use the full range — don't cluster "
        f"around the middle. 90+ = exact match, 75-89 = strong fit, 60-74 = "
        f"decent, 40-59 = neutral, 0-39 = not a fit. You do NOT choose like vs "
        f"skip — the harness decides that from fit_score. When genuinely "
        f"ambiguous, lean toward a lower score.\n"
    )


def _age_clause(age_min: int | None, age_max: int | None) -> str:
    if age_min is None and age_max is None:
        return ""
    lo = age_min if age_min is not None else 18
    hi = age_max if age_max is not None else 99
    return (
        f"\nAGE GATE: only score as a fit if the profile's stated age is "
        f"between {lo} and {hi} inclusive. Bumble shows the age next to the "
        f"name. If age is visible and out of range, set fit_score=0 and "
        f"dominant_factor=\"age\" so the harness skips it. If age genuinely "
        f"isn't visible across any frame, proceed with the normal rubric.\n"
    )


def _location_clause() -> str:
    """Tell the model to disregard location.

    Dropping "location" from the profile-info list isn't enough on its own:
    Bumble renders a distance and often a city right in the basic info, so
    the judge reads them off the screenshots whether or not we name the
    field. This clause is the half that actually does the work.

    Same clause as the Hinge sibling repo, minus its closing "or the opener
    you draft" — Bumble has no message step for the judge to draft into.
    """
    return (
        "\nLOCATION: ignore it. City and distance "
        '("3 miles away") are decoration — never let them affect fit_score, '
        "and don't mention them in your reasoning.\n"
    )


def build_system_prompt() -> str:
    volume = getattr(config, "SWIPE_VOLUME_GUIDANCE", None)
    if volume is None:
        volume = DEFAULT_VOLUME_GUIDANCE
    return SYSTEM_PROMPT_TEMPLATE.format(
        preferences=config.PREFERENCES.strip(),
        age_clause=_age_clause(config.AGE_MIN, config.AGE_MAX),
        location_clause=_location_clause(),
        fit_clause=_fit_clause(),
        volume_guidance=volume.strip(),
    )


def apply_fit_threshold(decision: Decision) -> Decision:
    """Decide like/skip entirely from fit_score and the FIT_SCORE_MIN dial.

    The model never chooses like vs skip — it only scores each profile. This
    is the single place the run decides: like iff fit_score >=
    config.FIT_SCORE_MIN. NOT_A_PROFILE is preserved so dialog/popup recovery
    keeps working. Clamps fit_score to 0-100 and mutates + returns
    `decision`.
    """
    if decision.decision == "NOT_A_PROFILE":
        return decision
    try:
        score = max(0, min(100, int(decision.fit_score)))
    except (TypeError, ValueError):
        print(f"[judge] WARN: invalid fit_score={decision.fit_score!r}, defaulting to 0")
        score = 0
    decision.fit_score = score
    decision.decision = "like" if score >= config.FIT_SCORE_MIN else "skip"
    return decision


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
