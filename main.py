"""BumbleAuto orchestrator.

Loop: capture profile frames -> ask model -> tap like or skip -> repeat.
"""

import argparse
import hashlib
import random
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

import io

from PIL import Image

import adb
import config
import metrics
import report
import vision
from judge_common import (apply_fit_threshold, is_fatal_judge_error,
                          is_network_error, load_backend)

judge = load_backend().judge


def _profile_region_hash(png: bytes) -> str:
    """md5 over a cropped region of the frame, excluding status bar (clock
    ticks every minute) and bottom nav (badges flicker). Two screenshots
    of the same profile taken 60+ seconds apart should produce the same
    hash; two different profiles should always differ."""
    img = Image.open(io.BytesIO(png))
    w, h = img.size
    crop = img.crop((0, 120, w, h - 220))
    return hashlib.md5(crop.tobytes()).hexdigest()


def capture_profile() -> list[bytes]:
    """Scroll through the current profile, returning a list of PNG frames.

    Takes FRAMES_PER_PROFILE screenshots with scrolls between, then does
    one final scroll to reach the bottom action buttons.
    """
    # Check for stuck loading screen BEFORE any scrolls or interactions.
    # Saves ~3-8 wasted scroll-up swipes + avoids burning API credits
    # judging a loading screen as if it were a profile. The caller catches
    # this and restarts the app.
    if vision.is_app_loading(adb.screenshot()):
        raise RuntimeError("app stuck on loading screen")

    frames: list[bytes] = []
    frames.append(adb.screenshot())
    adb.jitter_sleep("after_screenshot")

    for _ in range(config.FRAMES_PER_PROFILE - 1):
        adb.scroll_down()
        adb.jitter_sleep("after_scroll")
        frames.append(adb.screenshot())
        adb.jitter_sleep("after_screenshot")

    # Final scroll to reach the like/skip buttons at the bottom
    adb.scroll_down()
    adb.jitter_sleep("after_scroll")

    return frames


def do_skip() -> None:
    """Swipe left to skip the profile.

    Always swipes, even in dry run — advancing is needed for the loop
    to see new profiles. Start/end positions and duration are jittered
    to avoid looking robotic.
    """
    c = config.COORDS
    scale = random.uniform(0.85, 1.15)
    # Jitter start/end positions slightly (up to ±20px)
    jitter = lambda: random.randint(-15, 15)
    sx = int(c["swipe_skip_from"][0] + jitter())
    sy = int(c["swipe_skip_from"][1] + jitter())
    ex = int(c["swipe_skip_to"][0] + jitter())
    ey = int(c["swipe_skip_to"][1] + jitter())
    dur = int(c["swipe_duration_ms"] * scale)
    adb.swipe(sx, sy, ex, ey, dur)
    adb.jitter_sleep("after_skip")


class FeedAlreadyAdvanced(RuntimeError):
    """do_like aborted *after* the feed moved on — this profile is spent.

    The like swipe advances the feed, so anything that fails afterwards (the
    match-dismiss tap) leaves the next profile already on screen. main's
    do_like handler treats any failure as "recover by skipping this profile",
    so a plain RuntimeError there made it tap skip a second time — spending
    the *next* profile too, one the judge never saw. Raising a distinct type
    lets the handler tell "the feed already moved" from "the like failed and
    nothing has moved yet".
    """


def do_like() -> None:
    """Swipe right to like the profile.

    In dry run: swipe left instead (advance without spending a like).

    After the swipe, taps the match-dismiss area in case we matched
    (Bumble shows the "What a match!" screen after matching).
    If no match screen appeared, the tap lands harmlessly.
    Start/end positions and duration are jittered to avoid looking robotic.
    """
    if config.DRY_RUN:
        do_skip()
        return
    c = config.COORDS
    scale = random.uniform(0.85, 1.15)
    jitter = lambda: random.randint(-15, 15)
    sx = int(c["swipe_like_from"][0] + jitter())
    sy = int(c["swipe_like_from"][1] + jitter())
    ex = int(c["swipe_like_to"][0] + jitter())
    ey = int(c["swipe_like_to"][1] + jitter())
    dur = int(c["swipe_duration_ms"] * scale)
    adb.swipe(sx, sy, ex, ey, dur)
    adb.jitter_sleep("after_like_sent")

    # Always attempt to dismiss a potential match popup
    dx, dy = config.COORDS["match_dismiss"]
    try:
        adb.tap(dx, dy)
    except Exception as e:
        # The like already landed, so the feed has moved on. Tell the caller
        # not to "recover" by skipping — that would spend the next profile.
        raise FeedAlreadyAdvanced(
            f"match-dismiss tap failed after a sent like: {e!r}"
        ) from e
    adb.jitter_sleep("after_tap")


def save_error_screenshot(context: str) -> str:
    """Capture the current screen and save to <DEBUG_DIR>/errors/ for post-mortem.

    Returns the path to the saved screenshot."""
    errors_dir = config.DEBUG_DIR / "errors"
    errors_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    png = adb.screenshot()
    path = errors_dir / f"{ts}_{context}.png"
    path.write_bytes(png)
    return str(path)


def _recover_from_dialog() -> None:
    """Attempt to dismiss a dialog by pressing back once."""
    adb.press_back()
    time.sleep(1.0)


def save_debug(frames: list[bytes], decision, profile_idx: int) -> str | None:
    if not config.SAVE_DEBUG_FRAMES:
        return None
    bucket = "liked" if decision.decision == "like" else "skipped"
    bucket_dir = config.DEBUG_DIR / bucket
    bucket_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^a-z0-9]", "", (decision.name or "unknown").lower()) or "unknown"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    folder = bucket_dir / f"{ts}_{profile_idx:02d}_{safe_name}"
    imgs = folder / "imgs"
    imgs.mkdir(parents=True, exist_ok=True)
    for i, png in enumerate(frames):
        (imgs / f"frame_{i:02d}.png").write_bytes(png)
    (folder / "decision.txt").write_text(

        f"name: {decision.name}\n"
        f"decision: {decision.decision}\n"
        f"fit_score: {decision.fit_score}\n"
        f"confidence: {decision.confidence}\n"
        f"reasoning: {decision.reasoning}\n"
        f"dominant_factor: {decision.dominant_factor}\n"
        f"timestamp: {datetime.now().isoformat(timespec='seconds')}\n"
    )
    return folder.name


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BumbleAuto loop runner")
    p.add_argument(
        "--mode",
        default=None,
        help="Override config.ACTIVE_MODE for this run (one-shot). "
             "Must match a file under modes/<name>.py.",
    )
    return p.parse_args(argv)


def main() -> int:
    args = _parse_args()
    load_dotenv()

    if args.mode:
        config.ACTIVE_MODE = args.mode
        config._apply_mode()

    serial = adb.check_device()
    print(f"Connected to: {serial}")
    age_band = (
        f"age {config.AGE_MIN}-{config.AGE_MAX}"
        if (config.AGE_MIN is not None or config.AGE_MAX is not None)
        else "no age gate"
    )
    print(f"Mode:     {config.MODE_NAME} ({age_band})")
    print(f"Run:      {'DRY RUN (no taps)' if config.DRY_RUN else 'LIVE (will tap)'}")
    session_like_cap = random.randint(
        config.SESSION_LIKE_MIN,
        config.MAX_LIKES_PER_SESSION,
    )
    print(f"Max likes: {session_like_cap} (randomized "
          f"{config.SESSION_LIKE_MIN}-{config.MAX_LIKES_PER_SESSION}), "
          f"max profiles: {config.MAX_PROFILES_PER_SESSION}")

    if session_like_cap == 0:
        print("Cap is 0 — skipping this session.")
        return 0

    # Wake screen and launch Bumble
    adb.wake_screen()
    adb.launch_app("com.bumble.app")
    # Tap the center nav to ensure we're on the main swipe feed
    nx, ny = config.COORDS["nav_swipe"]
    adb.tap(nx, ny)
    time.sleep(2)

    likes_sent = 0
    skips = 0
    profiles_seen = 0
    total_cost = 0.0
    total_seconds = 0.0
    fit_score_sum = 0
    fit_score_count = 0
    liked_profiles: list[dict] = []  # tracked for the webhook report
    last_frame0_hash: str | None = None
    duplicate_streak = 0
    dialog_streak = 0
    hit_like_cap = False

    # Set by every path that ends the run on a failure, then consumed once
    # at the bottom of main() to pick the webhook post. Reports used to go
    # out at the failure site and the loop would still fall through to the
    # success post, so an aborted run arrived as a red error *and* a green
    # "Run Complete".
    abort_reason: str | None = None
    abort_screenshot: str | None = None

    while profiles_seen < config.MAX_PROFILES_PER_SESSION:
        profiles_seen += 1
        print(f"\n--- Profile {profiles_seen} ---")

        t0 = time.monotonic()
        try:
            frames = capture_profile()
        except RuntimeError as e:
            if "loading screen" in str(e):
                dialog_streak += 1
                print(f"\nAPP STUCK ON LOADING SCREEN (streak {dialog_streak})")
                dialog_ss = save_error_screenshot(f"loading-screen-{dialog_streak}")

                # Back press won't help an unloaded app — go straight to restart.
                if dialog_streak >= 3:
                    msg = (f"Loading screen persisted after {dialog_streak} "
                           f"app restarts.")
                    print(f"GIVING UP: {msg}")
                    abort_reason = msg
                    abort_screenshot = dialog_ss
                    break

                print(f"  Force-stopping + relaunching Bumble...")
                adb.force_stop_app("com.bumble.app")
                time.sleep(2)
                adb.wake_screen()
                adb.launch_app("com.bumble.app")
                adb.tap(*config.COORDS["nav_swipe"])
                time.sleep(3)

                # This iteration never judged a profile — refund it so the
                # session's profile budget isn't spent on app restarts.
                profiles_seen -= 1
                last_frame0_hash = None
                duplicate_streak = 0
                continue
            raise
        t_capture = time.monotonic() - t0
        print(f"Captured {len(frames)} frames")

        # If frame 0 is identical to the previous profile's frame 0, Bumble
        # didn't advance after our last action — force-skip rather than
        # burning another ~$0.035 re-judging the same person. Escalate the
        # delay if we keep duplicating, in case Bumble needs a beat to
        # recover from an "out of likes" / popup state.
        #
        # Hash a cropped region of frame 0 (excluding status bar at top and
        # nav bar at bottom). The status-bar clock ticks every minute and
        # the nav-bar can show transient badges; both make raw-bytes md5
        # diverge across iterations even when the *profile* is identical,
        # which silently breaks duplicate detection. Cropping isolates the
        # part of the screen that actually identifies the profile.
        frame0_hash = _profile_region_hash(frames[0])
        if frame0_hash == last_frame0_hash:
            duplicate_streak += 1
            print(f"DUPLICATE: frame 0 matches previous profile "
                  f"(streak {duplicate_streak}). Force-skipping without judge.")
            try:
                do_skip()
            except Exception as e:
                print(f"Skip failed during duplicate recovery: {e!r}")
            time.sleep(min(2 + duplicate_streak * 2, 15))
            continue
        last_frame0_hash = frame0_hash
        duplicate_streak = 0

        # Random profile dwell — simulates actually reading
        dwell = random.uniform(2, 8)
        print(f"  Reading profile for {dwell:.1f}s...")
        time.sleep(dwell)

        t1 = time.monotonic()
        decision = None
        fatal_error = None
        network_error = None
        for attempt in range(3):
            try:
                decision = judge(frames)
                break
            except Exception as e:
                err = repr(e)
                print(f"Judge attempt {attempt + 1}/3 failed: {e}")
                # Halt on errors that won't recover with a retry — burning
                # through Bumble swipes blind (force-skipping every profile
                # without a real decision) eats the daily quota and looks
                # robotic to Bumble. Classification keys off HTTP status and
                # walks the exception chain, so it covers every backend
                # instead of matching one vendor's wording.
                if is_fatal_judge_error(e):
                    fatal_error = err
                    break
                # A network error is different in kind: it usually clears on
                # its own, so it doesn't cut the attempts short. But if it
                # outlasts all three, the internet is down — and skipping is
                # the wrong recovery, because the judge never saw this
                # profile and the skip would spend it for nothing.
                if is_network_error(e):
                    network_error = err
                if attempt < 2:
                    time.sleep(5 * (attempt + 1))
        if fatal_error is not None:
            print(f"\nFATAL judge error — halting loop instead of burning "
                  f"Bumble swipes:\n  {fatal_error}")
            abort_reason = ("Fatal judge error — halted instead of burning "
                            f"Bumble swipes.\n{fatal_error}")
            break
        t_judge = time.monotonic() - t1
        if decision is None:
            if network_error is not None:
                print(f"\nNETWORK ERROR on all 3 judge attempts — ending the "
                      f"run. Nothing was skipped; the next cron slot resumes "
                      f"from this profile.\n  {network_error}")
                abort_reason = ("Network error on all 3 judge attempts — "
                                "nothing was skipped; the next cron slot "
                                f"resumes from this profile.\n{network_error}")
                break
            print("Judge failed 3 times — skipping this profile to keep the loop alive.")
            do_skip()
            continue

        print(f"Name:     {decision.name}")

        # ── Pickiness gate: like iff fit_score >= FIT_SCORE_MIN ──
        # The model scores; the harness decides. Keeping the threshold out of
        # the prompt is deliberate — the model can't game a number it never
        # sees, and re-tuning pickiness is a config edit, not a prompt edit.
        # NOT_A_PROFILE passes through untouched so recovery below still fires.
        decision = apply_fit_threshold(decision)

        # dominant_factor is symmetric — it names what drove the score in
        # either direction, so a like reports it too.
        print(f"Decision: {decision.decision} ({decision.confidence}) "
              f"[{decision.dominant_factor}]")
        print(f"Fit:      {decision.fit_score}/100 "
              f"(threshold {config.FIT_SCORE_MIN})")
        print(f"Reason:   {decision.reasoning}")

        # ── Dialog / popup detection & recovery ──
        # Bumble shows these often enough (upsells, notification prompts,
        # "out of likes") that treating one as a scorable profile would spend
        # a swipe on a screen that isn't a person. Each tier is tried once,
        # escalating, and gives up rather than looping forever.
        if decision.decision == "NOT_A_PROFILE":
            dialog_streak += 1
            print(f"\nDIALOG DETECTED (streak {dialog_streak}): "
                  f"{decision.reasoning[:120]}")
            dialog_ss = save_error_screenshot(f"dialog-streak-{dialog_streak}")

            if dialog_streak == 1:
                # ── Tier 1: press back to dismiss ──
                print("  Tier 1: pressing back to dismiss...")
                _recover_from_dialog()
            elif dialog_streak == 2:
                # ── Tier 2: force-stop + relaunch ──
                print("  Tier 2: force-stopping + relaunching Bumble...")
                adb.force_stop_app("com.bumble.app")
                time.sleep(1.5)
                adb.wake_screen()
                adb.launch_app("com.bumble.app")
                # Return to the swipe feed rather than whatever tab the app
                # reopened on.
                adb.tap(*config.COORDS["nav_swipe"])
                time.sleep(3)
            else:
                # ── Tier 3: give up ──
                msg = (f"Dialog recovery failed after back button + app restart. "
                       f"Last reason: {decision.reasoning[:200]}")
                print(f"TIER 3: {msg}")
                abort_reason = msg
                abort_screenshot = dialog_ss
                break

            # This iteration never evaluated a profile — refund it, and clear
            # the duplicate baseline so the post-recovery screen isn't mistaken
            # for a repeat of the pre-recovery one.
            profiles_seen -= 1
            last_frame0_hash = None
            duplicate_streak = 0
            continue
        else:
            dialog_streak = 0

        fit_score_sum += decision.fit_score
        fit_score_count += 1

        folder_name = save_debug(frames, decision, profiles_seen)

        t2 = time.monotonic()
        if decision.decision == "like":
            like_sent = False
            try:
                do_like()
                like_sent = True
            except FeedAlreadyAdvanced as e:
                # The swipe itself landed and the feed moved on — only the
                # post-swipe cleanup tap failed. This is the like it was, so
                # count it. The handler below would "recover by skipping",
                # which spends the *next* profile, one no judge ever scored.
                print(f"do_like aborted: {e} — feed already advanced, "
                      f"counting it as the like it was.")
                like_sent = True
            except Exception as e:
                save_error_screenshot(f"do-like-failed-{profiles_seen}")
                print(f"do_like failed: {e!r} — recovering by skipping this profile.")
                try:
                    do_skip()
                except Exception as e2:
                    print(f"do_skip recovery also failed: {e2!r} — loop will retry next iter.")
                skips += 1
            if like_sent:
                liked_profiles.append({
                    "name": decision.name,
                    "index": profiles_seen,
                    "folder": folder_name,
                    "fit_score": decision.fit_score,
                })
                likes_sent += 1
                if likes_sent >= session_like_cap:
                    print(f"Hit max likes cap ({session_like_cap}). Stopping.")
                    # Don't break here — the profile still needs its log
                    # record + cost tally below (metrics.log_profile).
                    hit_like_cap = True
        else:
            do_skip()
            skips += 1
        t_act = time.monotonic() - t2

        timing = {
            "capture_seconds": round(t_capture, 2),
            "judge_seconds":   round(t_judge, 2),
            "act_seconds":     round(t_act, 2),
            "total_seconds":   round(t_capture + t_judge + t_act, 2),
        }
        metrics.log_profile(profiles_seen, decision, timing)
        total_cost += metrics.estimated_cost(decision.usage)
        total_seconds += timing["total_seconds"]
        avg_fit = (fit_score_sum / fit_score_count) if fit_score_count else 0
        metrics.print_running_totals(
            profiles_seen, likes_sent, skips, total_cost, total_seconds,
            avg_fit_score=avg_fit,
        )

        if hit_like_cap:
            break

    avg_fit = (fit_score_sum / fit_score_count) if fit_score_count else 0
    print(f"\nDone. {likes_sent} likes sent across {profiles_seen} profiles "
          f"(avg fit {avg_fit:.0f}/100).")

    # Exactly one post per run — error or success, never both.
    if abort_reason is not None:
        report.post_error(abort_reason, profiles_seen, likes_sent, skips,
                          screenshot_path=abort_screenshot)
    else:
        report.post_run(likes_sent, profiles_seen, skips, total_cost,
                        total_seconds, liked_profiles, avg_fit_score=avg_fit)

    # Cleanup: force-stop Bumble so next run starts fresh regardless of app state,
    # then turn screen off.
    adb.force_stop_app("com.bumble.app")
    adb.turn_screen_off()

    # An aborted run is not a success. This used to return 0 either way, so
    # cron.log read "Done (exit 0)" for a run that died halfway — the exit
    # code was the one signal the webhook couldn't stand in for.
    return 1 if abort_reason is not None else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        report.post_crash(tb)
        sys.exit(1)
