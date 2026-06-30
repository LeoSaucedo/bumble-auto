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

    # Scroll gesture (swipe up = scroll down through profile).
    "scroll_from":       (360, 1125),
    "scroll_to":         (360, 765),
    "scroll_duration_ms": 350,

    # Match popup dismiss (top-left X after matching).
    "match_dismiss":     (48, 95),     # calibrated 2026-06-29

    # Bottom nav icons.
    "nav_swipe":         (180, 1498),
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
# "gemini"    -> uses Gemini via GEMINI_API_KEY; cheapest option.
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
# Uses gemini-3.1-flash-lite by default (cheapest vision model). Override
# via GEMINI_MODEL env var or edit the default below.
GEMINI_MODEL = "gemini-3.1-flash-lite"

# ---------- Swipe volume guidance ----------
# Injected into the system prompt to guide how aggressively the judge
# swipes right. None = use DEFAULT_VOLUME_GUIDANCE from judge_common.py.
# Set to a custom string to override the default guidance.
SWIPE_VOLUME_GUIDANCE: str | None = None

# ---------- Paths ----------
BASE_DIR = Path(__file__).parent
DEBUG_DIR = BASE_DIR / "debug"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
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


def _apply_mode() -> None:
    """Resolve ACTIVE_MODE and populate this module's PREFERENCES /
    AGE_MIN / AGE_MAX / MODE_NAME / cap overrides.

    Re-entrant — main.py calls this again after parsing --mode so a CLI
    override takes effect before the judge sees config.
    """
    import modes
    mode = modes.load(ACTIVE_MODE)
    g = globals()
    g["PREFERENCES"] = mode.PREFERENCES
    g["AGE_MIN"] = getattr(mode, "AGE_MIN", None)
    g["AGE_MAX"] = getattr(mode, "AGE_MAX", None)
    g["MODE_NAME"] = mode.NAME
    for k in ("MAX_LIKES_PER_SESSION", "MAX_PROFILES_PER_SESSION"):
        v = getattr(mode, k, None)
        if v is not None:
            g[k] = v


_apply_mode()
