"""One-off: scroll to the top, then progressively capture frames top-to-bottom."""

import shutil
import time

import adb
import config

# config.DEBUG_DIR rather than ./debug: the capture corpus is large enough
# that it gets pointed at a separate disk, and this tool should follow it
# there instead of quietly filling the repo's own filesystem.
out = config.DEBUG_DIR / "full_profile"
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)

adb.check_device()

# Reset: scroll up 8 times to guarantee we land at the top
print("Scrolling to top...")
for _ in range(8):
    adb.scroll_up()
    time.sleep(0.4)

time.sleep(1.0)

# Capture frame 0 at the top
(out / "frame_00.png").write_bytes(adb.screenshot())
print("frame_00 saved (top)")

# Smaller scrolls (1000px instead of 1200px) for better overlap between frames
NUM_FRAMES = 7
for i in range(1, NUM_FRAMES):
    adb.swipe(540, 1700, 540, 700, 350)
    time.sleep(0.9)
    (out / f"frame_{i:02d}.png").write_bytes(adb.screenshot())
    print(f"frame_{i:02d} saved")

print(f"\nDone -> {out}")
