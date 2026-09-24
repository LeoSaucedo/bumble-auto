"""Screen-state checks that need actual pixels.

Most of this repo drives Bumble by coordinates — the swipe and scroll
gestures in `adb.py` are blind. The exception is telling a loading screen
apart from a real profile, which can only be answered by looking at the
frame. Mirrors the equivalent helper in the Hinge sibling repo so the two
stay in step (see `is_app_loading` for the one constant that legitimately
differs between them).
"""

import io

import numpy as np
from PIL import Image

import config


def is_app_loading(png: bytes) -> bool:
    """Check if Bumble is stuck on the loading/splash screen.

    The loading screen is a white backdrop with a small animated logo
    in the center — the animation creates some pixel variation at
    center, but the overwhelming majority of the content area is still
    near-white. A loaded profile has a photo card, text overlays, and
    UI buttons that fill most of the screen with non-white pixels.

    Uses a simple white-pixel ratio across the full content area
    (excluding status bar and nav bar). If >75% of pixels are
    near-white (>=230), it's a loading screen. On a real profile,
    photos and text bring this well below 50%.

    Measured on the shipped Moto e20 (720x1600): splash = 0.98,
    loaded feed = 0.12, so the threshold sits in a wide empty gap.
    """
    im = np.array(Image.open(io.BytesIO(png)).convert("L"))
    h, w = im.shape

    # Full-screen sanity check — reject thumbnails and crops. Expressed
    # against the configured device rather than the Hinge sibling's
    # hard-coded "w < 950", which is right for its 1080-wide reference
    # phone but is true of every frame a 720-wide device produces, making
    # the white-ratio test below unreachable. The mechanism is identical
    # in both repos; only this constant tracks the hardware.
    if h < config.SCREEN_HEIGHT * 0.9 or w < config.SCREEN_WIDTH * 0.9:
        return False

    # Full content area: exclude status bar (~y=0-150) and nav bar
    # (~bottom 250px). The animated logo occupies a small fraction of
    # this region — it won't push white_ratio below the threshold.
    content = im[150:h - 250, 50:w - 50]
    if content.size == 0:
        return False

    white_ratio = (content > 230).mean()
    return white_ratio > 0.75
