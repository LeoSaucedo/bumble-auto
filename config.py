"""Configuration for BumbleAuto.

PREFERENCES and AGE_MIN/MAX come from the active mode (see
`modes/`). Set ACTIVE_MODE here for the persistent default; override per-run
via `python main.py --mode <name>`.

The COORDS defaults are **placeholders** — update with real Bumble coords
after running calibrate.py against the Bumble UI.

.env variables override every config.py value at import time.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ---------- Mode selection ----------
ACTIVE_MODE = "example_lenient"

# These get filled in by _apply_mode() at the bottom of this file.
PREFERENCES: str = ""
AGE_MIN: int | None = None
AGE_MAX: int | None = None
MODE_NAME: str = ""

# ---------- Run mode ----------
DRY_RUN = False

# Each session picks a random like cap between SESSION_LIKE_MIN and
# MAX_LIKES_PER_SESSION. With Bumble, run higher volume: swipe roughly
# half the profiles (see SWIPE_VOLUME_GUIDANCE in judge_common.py).
MAX_LIKES_PER_SESSION = 20
SESSION_LIKE_MIN = 5
MAX_PROFILES_PER_SESSION = 100

# ---------- Device settings ----------
SCREEN_WIDTH = 720
SCREEN_HEIGHT = 1600

# Number of scroll-and-screenshot passes per profile.
FRAMES_PER_PROFILE = 7

# ---------- Coordinates ----------
# *** PLACEHOLDERS — replace with real Bumble coords ***
COORDS = {
    # Swipe action targets (bottom of profile after scrolling)
    "skip_button":       (180, 1400),   # X icon
    "like_button":       (540, 1400),   # Heart icon

    # Scroll gesture (swipe up = scroll down through profile)
    "scroll_from":       (360, 1125),
    "scroll_to":         (360, 465),
    "scroll_duration_ms": 350,

    # Bottom nav
    "nav_swipe":         (180, 1498),
    # --- todo: fill remaining nav coords ---
}

# ---------- Timing ----------
DELAYS = {
    "after_scroll":     (0.6, 1.0),
    "after_screenshot": (0.2, 0.4),
    "after_tap":        (0.3, 0.6),
    "after_like_sent":  (1.5, 2.5),
    "after_skip":       (1.0, 1.5),
}

# ---------- Judge backend ----------
JUDGE_BACKEND = "anthropic"

# ---------- Anthropic settings ----------
MODEL = "claude-sonnet-4-6"
EFFORT = "medium"

# ---------- Ollama settings ----------
OLLAMA_MODEL = "qwen2.5-vl"
OLLAMA_HOST = None

# ---------- Gemini settings ----------
GEMINI_MODEL = "gemini-3.1-flash-lite"

# ---------- Volume guidance ----------
# Injected into the system prompt to control how aggressively to swipe right.
# None = use DEFAULT_VOLUME_GUIDANCE from judge_common.py.
SWIPE_VOLUME_GUIDANCE: str | None = None

# ---------- Paths ----------
BASE_DIR = Path(__file__).parent
DEBUG_DIR = BASE_DIR / "debug"
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
SAVE_DEBUG_FRAMES = True

# ---------- .env overrides ----------
load_dotenv()


def _apply_env_overrides() -> None:
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
