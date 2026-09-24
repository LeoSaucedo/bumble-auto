"""Configuration for BumbleAuto.

PREFERENCES, AGE_MIN/MAX come from the active mode (see
`modes/`). Set ACTIVE_MODE here for the persistent default; override per-run
via `python main.py --mode <name>`.

The COORDS defaults below are **placeholders** — update with real Bumble
coords after running calibrate.py against the app.

.env variables override every config.py value at import time.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------- Mode selection ----------
# Which `modes/<name>.py` to load. Overridden per-run by `python main.py --mode X`.
ACTIVE_MODE = "example_lenient"

# These get filled in by _apply_mode() at the bottom of this file. Declared
# here so static analyzers / IDEs see them. Do not edit by hand — edit the
# mode module instead.
PREFERENCES: str = ""
AGE_MIN: int | None = None
AGE_MAX: int | None = None
MODE_NAME: str = ""

# ---------- Run mode ----------
# DRY_RUN = False -> actually swipe like or skip (default)
# DRY_RUN = True  -> decide and log, but force-skip every profile
#                    instead of liking. Every "would-like" profile gets
#                    skipped (gone from your queue) but no likes are
#                    spent.
#
# When to flip this to True:
#   - Bumble free tier (limited swipes): YES, for your first run or two.
#     Lets you watch decisions without spending your daily cap on a rubric
#     you haven't tuned. Once decisions look right, flip back to False.
#   - Bumble+ (unlimited swipes): NO. Just run small live batches
#     (MAX_LIKES_PER_SESSION = 10) and Ctrl-C if something looks off.
DRY_RUN = False

# Default = 20, which balances volume with battery/memory on the phone.
# With Bumble, there's no message to write, so volume can be much higher
# than Hinge. One session processes profiles until the cap or limit.
#
# If you have Bumble+ (no daily cap), bump this to ~30-50 per session and
# run multiple sessions throughout the day. Going much higher per session
# tends to trigger Bumble's soft-throttle (empty stack after a burst);
# spacing batches across the day works better than one giant batch.
#
# SESSION_LIKE_MIN sets the floor for random jitter. Each session picks a
# random cap between SESSION_LIKE_MIN and MAX_LIKES_PER_SESSION so the
# like count varies per session — looks more human.
MAX_LIKES_PER_SESSION = 20
SESSION_LIKE_MIN = 5
MAX_PROFILES_PER_SESSION = 100

# ---------- Pickiness (fit score gate) ----------
# The judge returns a fit_score (0-100) for every profile and never chooses
# like vs skip itself. The harness decides LIKE iff fit_score >=
# FIT_SCORE_MIN, else SKIP. Raise this to be pickier (fewer likes, higher
# average quality); lower it for more volume. A mode file may set its own
# FIT_SCORE_MIN to make just that mode pickier — that's the right lever for
# "be selective" rubrics, since it's enforced rather than merely suggested.
# Env override: FIT_SCORE_MIN in .env.
FIT_SCORE_MIN = 50

# ---------- Device settings ----------
# Moto e20 real phone is 720x1600. Change if using a different device.
SCREEN_WIDTH = 720
SCREEN_HEIGHT = 1600

# Number of scroll-and-screenshot passes per profile.
# Longer profiles (6 photos + 3 prompts) need ~7 frames at the scroll step
# below. Duplicate end frames on shorter profiles are harmless.
FRAMES_PER_PROFILE = 7

# ---------- Coordinates ----------
# *** PLACEHOLDERS — replace with real Bumble coords ***
# Run `python calibrate.py` to verify/adjust after any Bumble UI update.
COORDS = {
    # Swipe action targets (bottom of profile after scrolling through).
    # On Bumble, the heart (like) and X (skip) buttons are always at the
    # bottom after scrolling through all profile photos and prompts.
    "skip_button":       (126, 998),   # X icon (calibrated 2026-06-29)
    "like_button":       (595, 1000),  # Heart icon (calibrated 2026-06-29)

    # Swipe gesture coords (horizontal swipe instead of button taps).
    # Swipe at vertical center of screen (y=800 on 720x1600).
    # 80% of width (576) → 20% (144) for swipe left (skip).
    # 20% (144) → 80% (576) for swipe right (like).
    "swipe_skip_from":   (576, 800),
    "swipe_skip_to":     (144, 800),
    "swipe_like_from":   (144, 800),
    "swipe_like_to":     (576, 800),
    "swipe_duration_ms": 200,

    # Scroll gesture (swipe up = scroll down through profile). Only the y
    # values are read: the live x is re-randomized per gesture within a
    # safe band (adb._scroll_span), and both endpoints get a little y
    # jitter so repeated swipes aren't identical.
    "scroll_from":       (360, 1125),
    "scroll_to":         (360, 375),
    "scroll_duration_ms": 500,

    # Match popup dismiss (top-left X after matching).
    "match_dismiss":     (48, 95),     # calibrated 2026-06-29

    # Bottom nav icons.
    "nav_swipe":         (360, 1498),
    # --- todo: fill remaining nav coords ---
}

# ---------- Timing ----------
# Random delay between actions (seconds, min/max for jitter).
DELAYS = {
    "after_scroll":     (0.6, 1.0),
    "after_screenshot": (0.2, 0.4),
    "after_tap":        (0.3, 0.6),
    "after_like_sent":  (1.5, 2.5),
    "after_skip":       (1.0, 1.5),
}

# ---------- Judge backend ----------
# "anthropic" -> uses your ANTHROPIC_API_KEY; best quality, ~$0.02-0.05/profile.
# "ollama"    -> uses Ollama Cloud (free tier) or local Ollama; lower quality
#                but no per-token cost.
# "gemini"    -> uses Gemini via GEMINI_API_KEY; cheap, good quality.
# "deepseek"  -> uses DeepSeek via DEEPSEEK_API_KEY; cheap vision backend.
JUDGE_BACKEND = "gemini"

# ---------- Anthropic settings (when JUDGE_BACKEND == "anthropic") ----------
# Sonnet is the default — cheaper than Opus and plenty capable for this task.
# Switch to "claude-opus-4-7" if you want top-quality judgment.
MODEL = "claude-sonnet-4-6"
EFFORT = "medium"  # low | medium | high

# ---------- Ollama settings (when JUDGE_BACKEND == "ollama") ----------
OLLAMA_MODEL = "qwen2.5-vl"
# OLLAMA_HOST: None or "" -> default http://localhost:11434
#              "https://ollama.com" -> Ollama Cloud (requires OLLAMA_API_KEY)
OLLAMA_HOST = None

# ---------- Gemini settings (when JUDGE_BACKEND == "gemini") ----------
# GEMINI_API_KEY must be set in .env or environment.
# Uses gemini-3.5-flash-lite by default — $0.30/$2.50 per 1M tokens, the
# cheapest vision model in the current lineup. Override via GEMINI_MODEL
# env var or edit the default below.
GEMINI_MODEL = "gemini-3.5-flash-lite"

# ---------- Swipe volume guidance ----------
# Injected into the system prompt to calibrate how the judge *scores*
# profiles — it no longer decides like vs skip (see FIT_SCORE_MIN above), so
# this is about using the 0-100 range honestly, not about a target like
# count. None = use DEFAULT_VOLUME_GUIDANCE from judge_common.py. Set to a
# custom string to override the default guidance, or set it in a mode file
# to give just that mode its own calibration. Private modes keep their
# personal tuning here rather than in this shared default.
SWIPE_VOLUME_GUIDANCE: str | None = None

# ---------- DeepSeek settings (when JUDGE_BACKEND == "deepseek") ----------
# DEEPSEEK_API_KEY must be set in .env or environment. The API is
# OpenAI-compatible (https://api.deepseek.com); see judge_deepseek.py.
#
# Models:
#   "deepseek-flash"   — DeepSeek-V4.1-Flash; vision-capable (default)
#   "deepseek-v4-pro"  — stronger, but NO vision — unusable for this repo
# Override via DEEPSEEK_MODEL env var or edit the default below.
DEEPSEEK_MODEL = "deepseek-flash"

# Thinking mode. Off by default: it's the only way to force the
# submit_decision tool call (the API rejects forced tool choice while
# thinking is on — see judge_deepseek.py). Turn it on for better
# reasoning on ambiguous profiles, at the cost of a prose-answer
# fallback path and a slower, pricier call.
DEEPSEEK_THINKING = False
# Only used when DEEPSEEK_THINKING = True. low | medium | high | max
# ("medium" is mapped to "high" by the API).
DEEPSEEK_REASONING_EFFORT = "low"

# ---------- Paths ----------
BASE_DIR = Path(__file__).parent
DEBUG_DIR = BASE_DIR / "debug"
SAVE_DEBUG_FRAMES = True  # keep frames + decisions in debug/ for review


# ---------- .env overrides ----------
load_dotenv()


def _apply_env_overrides() -> None:
    """Override any config module variable from .env.

    Add `KEY=*** to .env and it'll override the matching config.py
    variable at import time. Supports str, int, float, and bool types.
    """
    g = globals()
    for key, val in os.environ.items():
        current = g.get(key)
        if current is None:
            continue
        if isinstance(current, bool):
            g[key] = val.lower() in ("1", "true", "yes")
        elif isinstance(current, int):
            try:
                g[key] = int(val)
            except ValueError:
                print(f"[config] env {key}={val!r}: not a valid int, skipped")
        elif isinstance(current, float):
            try:
                g[key] = float(val)
            except ValueError:
                print(f"[config] env {key}={val!r}: not a valid float, skipped")
        else:
            g[key] = val


_apply_env_overrides()


# Keys a mode file may override. PREFERENCES / AGE_MIN / AGE_MAX / MODE_NAME
# are always assigned from the mode, so they can't leak; these four are
# assigned only when the mode actually defines them, which means a mode that
# omits one would otherwise inherit whatever the *previous* mode set.
#
# That matters on the `python main.py --mode X` path: _apply_mode() runs once
# at import (for .env's ACTIVE_MODE) and again after arg parsing, so with
# ACTIVE_MODE=carlos in .env, `--mode cougar` would silently inherit carlos's
# FIT_SCORE_MIN and SWIPE_VOLUME_GUIDANCE instead of the defaults. _apply_mode
# restores these from this snapshot before applying the mode's own values.
#
# The snapshot is taken after _apply_env_overrides(), so a .env value is the
# baseline a mode falls back to — setting FIT_SCORE_MIN in .env still works as
# a global default.
_MODE_OVERRIDABLE = (
    "MAX_LIKES_PER_SESSION",
    "MAX_PROFILES_PER_SESSION",
    "SWIPE_VOLUME_GUIDANCE",
    "FIT_SCORE_MIN",
)
_MODE_DEFAULTS = {_k: globals()[_k] for _k in _MODE_OVERRIDABLE}


def _apply_mode() -> None:
    """Resolve ACTIVE_MODE and populate this module's PREFERENCES /
    AGE_MIN / AGE_MAX / MODE_NAME and the _MODE_OVERRIDABLE tuning keys.

    Re-entrant — main.py calls this again after parsing --mode so a CLI
    override takes effect before the judge sees config. Each call resets the
    overridable keys to their defaults first, so switching modes can't leak
    the previous mode's tuning into the new one.
    """
    import modes
    mode = modes.load(ACTIVE_MODE)
    g = globals()
    g["PREFERENCES"] = mode.PREFERENCES
    g["AGE_MIN"] = getattr(mode, "AGE_MIN", None)
    g["AGE_MAX"] = getattr(mode, "AGE_MAX", None)
    g["MODE_NAME"] = mode.NAME
    for k in _MODE_OVERRIDABLE:
        v = getattr(mode, k, None)
        g[k] = _MODE_DEFAULTS[k] if v is None else v


_apply_mode()
