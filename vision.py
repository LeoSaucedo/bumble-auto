"""Screen-state checks that need actual pixels.

Most of this repo drives Bumble by coordinates — the swipe and scroll
gestures in `adb.py` are blind. The exception is telling a loading screen
apart from a real profile, which can only be answered by looking at the
frame. Mirrors the equivalent helper in the Hinge sibling repo so the two
stay in step.
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

    Measured on the shipped Moto e20 (720x1600) over 157 sampled
    captures: real profiles cluster at 0.17 median, splashes at 0.97,
    so the threshold sits in a wide empty gap. The Hinge sibling has
    far less headroom (real profile ~0.44 median, 0.62 max) because it
    floats each photo card on white where Bumble fills the screen with
    the photo — the same threshold, but a much tighter margin there.
    """
    im = np.array(Image.open(io.BytesIO(png)).convert("L"))
    h, w = im.shape

    # Full-screen sanity check — reject thumbnails and crops. Derived
    # from config rather than hard-coded, so it tracks the device if the
    # phone changes.
    #
    # The Hinge sibling hard-coded this to "h < 1500 or w < 950" until
    # 2026-09-24 — bounds written for the 1080-wide Pixel 10 it ran
    # before the Moto e20, and never rescaled when the device changed.
    # Every frame the e20 produces is 720 wide, so there the gate
    # returned False unconditionally and the white-ratio test below was
    # unreachable: the guard never fired once in the eight weeks it
    # existed. This repo was ported with the config-derived form, and
    # Hinge was then corrected to match it.
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
