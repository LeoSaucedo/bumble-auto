"""Saves a screenshot so you can read pixel coords for config.COORDS.

Open the resulting PNG in any image viewer that shows cursor position
(MS Paint, IrfanView, etc.) and hover over each UI element you need
to record.
"""

from pathlib import Path

import adb


def main() -> None:
    adb.check_device()
    path = Path(__file__).parent / "calibrate.png"
    path.write_bytes(adb.screenshot())
    print(f"Saved: {path}")
    print()
    print("Open the file and read pixel coords for:")
    print("  1. Skip gesture   -> COORDS['swipe_skip_from'] / ['swipe_skip_to']")
    print("     (right-to-left across the card, e.g. 80% width -> 20% width)")
    print("  2. Like gesture   -> COORDS['swipe_like_from'] / ['swipe_like_to']")
    print("     (left-to-right, the mirror of the skip gesture)")
    print("  3. Scroll gesture -> COORDS['scroll_from'] / ['scroll_to']")
    print("     (only y is read; x is re-randomized per swipe)")
    print("  4. Match dismiss  -> COORDS['match_dismiss']")
    print("     (top-left X on the 'What a match!' screen)")
    print("  5. Center nav item -> COORDS['nav_swipe']")
    print()
    print("Swipe y should sit inside the card, clear of the status bar and")
    print("the action row at the bottom. Keep swipe x away from the screen")
    print("edges so Android's back-gesture strip doesn't eat the swipe.")
    print()
    print("Then edit config.py.")


if __name__ == "__main__":
    main()
