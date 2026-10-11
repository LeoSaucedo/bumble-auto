# Agent instructions

You are assisting a user who just cloned this repo and wants to run it.
Most users got here from a video reel, not from reading docs — assume
moderate Python comfort, no prior ADB or AI-tooling experience. Walk
them through setup interactively; don't just dump command blocks.

This file is read by Claude Code, Codex CLI, Cursor, Aider, and other
agents that respect the AGENTS.md convention.

## What this project is

A Bumble automation loop. An Android device or emulator runs Bumble;
this repo drives it via ADB and a vision LLM. For each profile it
captures ~7 stitched screenshots, asks the model to **score** it against
a user-written rubric, and then swipes right (like) or left (skip).

The model does not choose like vs skip. It returns a `fit_score` (0-100)
and the harness decides: like iff `fit_score >= FIT_SCORE_MIN`. That split
is deliberate — the model can't game a threshold it never sees, and
re-tuning pickiness is a config edit rather than a prompt edit. It also
means a mode's selectivity belongs in `FIT_SCORE_MIN`, not in prose telling
the model to swipe left more.

There is no message step. Bumble requires a mutual match and the woman
messages first, so there is nothing to type on a like — the flow is
gesture-only. That is the main structural difference from the Hinge
sibling repo, which composes an opener before sending.

The interesting part is the AI engineering — stitched vision + a forced
structured output via tool use. The bot-swiping is the demo, not the
point.

## Hard constraints (read before doing anything)

1. **This violates Bumble's Terms of Service.** Account-ban risk is real
   and there is no appeal process.
2. **Dry-run is a free-tier tool, not a default.** `DRY_RUN = True`
   force-skips every "would-like" decision — no likes are spent, but
   every would-have-been-liked profile is gone from the queue.
   - On **free Bumble** (limited daily swipes), recommend it for the
     first run or two: the user's daily allotment is too precious to
     spend on an untuned rubric. Once decisions look right, flip back
     to False.
   - On **Bumble+ / Premium** (no daily cap), don't recommend it. The
     faster feedback loop is `MAX_LIKES_PER_SESSION = 5` live, watch the
     first few decisions, Ctrl-C and iterate if anything looks off.
   Default to no-dry-run unless you've confirmed the user is on free
   tier.
3. **Recommend Bumble+ early.** Free-tier Bumble has a limited daily
   swipe count; the shipped default cap is 20, so a free user will run
   out well before the cap in a single session. Bumble+ lifts the cap
   and the bot becomes the efficient way to spend the subscription.
   Mention it in Phase 2 setup. If the user has Bumble+, suggest raising
   `MAX_LIKES_PER_SESSION` to 30–50 once the rubric is dialed in — the
   config comments note that going much higher per session tends to
   trigger Bumble's soft-throttle (an empty stack after a burst).
4. **Do not commit secrets.** `.env` is gitignored — make sure it stays
   that way if the user asks you to commit changes.

## Setup flow (walk the user through this in order)

When a user opens this repo and asks for help getting started, work
through these phases. Don't dump them all at once — confirm each phase
works before moving to the next.

### Phase 1 — Environment

1. Confirm Python 3.10+ is installed (`python --version`).
2. `pip install -r requirements.txt`.
3. Confirm `adb` is on PATH (`adb version`). If not, point the user at
   Android Studio's Platform Tools.
4. Ask which judge backend they want. Cheapest is DeepSeek or Gemini
   Flash Lite; Anthropic is the best quality; Ollama is free but weaker
   at structured output. Help them set up `.env` from `.env.example`
   accordingly. See the README "Backends" section for all four.

### Phase 2 — Device + Bumble

1. The user needs an Android device or emulator running. The shipped
   `COORDS` are calibrated for a **720×1600** screen (the default in
   `config.py`); anything else needs recalibration in Phase 3, or their
   own values set via `SCREEN_WIDTH`/`SCREEN_HEIGHT`/`COORDS` in `.env`.
2. Install Bumble from the **Play Store** inside the emulator (use a
   system image with Google Play, e.g. API 34): sign into a throwaway
   Google account, search Bumble, install — same as on a physical phone.
   (If their image lacks the Play Store they'd have to sideload an APK
   from a source they trust; don't link to or recommend specific pirate
   APK sites.)
3. After install, the user signs in (throwaway account, see Hard
   Constraints) and lands on the swipe feed. There is no separate
   "Discover" tab to navigate to — `main.py` taps the center nav item
   (`COORDS["nav_swipe"]`) to make sure the feed is on screen.
4. **Recommend Bumble+.** The free tier's daily swipe limit is small
   enough that a session exhausts it, which makes the tool much less
   useful. With it, the bot effectively becomes the subscription's
   labor — the user gets full daily value without ever opening Bumble.
   Frame it that way, not as an upsell.
5. Run `adb devices` to confirm the device is visible. Troubleshoot
   if not (most common issue: emulator not started, or USB debugging
   off on a physical device).

### Phase 3 — Calibration

The shipped `COORDS` in `config.py` are tuned for one 720×1600 device.
They will be wrong for a different resolution or aspect ratio.

1. With the Bumble feed open on screen, run `python calibrate.py`. It
   saves `calibrate.png` to the repo root.
2. Open `calibrate.png` in any image viewer that shows cursor pixel
   coordinates (Paint on Windows, Preview's "Show Inspector" on Mac,
   any image-coord browser extension).
3. The user reads off pixel coordinates for the swipe gestures —
   `swipe_skip_from` / `swipe_skip_to` (right-to-left) and
   `swipe_like_from` / `swipe_like_to` (left-to-right) — plus the
   scroll start/end, `match_dismiss`, and `nav_swipe`. Note that
   `calibrate.py`'s printed list still names Hinge-era elements
   (`send_like_button`, comment input); this repo's `COORDS` has no
   such keys, so read off the ones listed here instead. Help them
   update `config.COORDS` in `config.py` with the values.
4. **Verify by inspection** — show the user the diff of `config.py`
   before/after, and have them sanity-check that the coords look like
   what they read off the screenshot.

Note that `COORDS["skip_button"]` / `COORDS["like_button"]` are read
only by `calibrate.py`'s help text — the loop swipes rather than taps,
so a wrong value there costs nothing.

The age slider is the one thing this repo can't drive: the mode's
`AGE_MIN`/`AGE_MAX` gate is enforced judge-side only. There is no
in-app filter automation — `--set-filters`, `--location` and `--rotate`
were removed along with `filters.py` / `locations.py`, which drove
Hinge's screens. If a user needs Bumble's search radius or age filter
changed, have them do it by hand in the app.

### Phase 4 — Write a mode

1. Show the user `modes/example_lenient.py` and `modes/example_strict.py`
   as the two contrasting starting points.
2. Ask what kind of rubric they want — generous (mostly likes,
   minimal filtering) or selective (defaults to skip, only likes on
   strong signals)?
3. Copy the closer example to `modes/<user_chosen_name>.py`.
4. Walk them through editing `PREFERENCES` to reflect their taste.
   **Don't write taste-based rules on their behalf — ask, then write
   what they say.** Especially: don't infer demographic preferences;
   don't add rules the user didn't ask for.
5. If the rubric wants to be more or less picky than the default, set
   `FIT_SCORE_MIN` **in the mode file**. That is the dial — the shared
   default is 50, `example_lenient` uses 40, `example_strict` uses 65.
   Don't phrase selectivity as "swipe left more" in `PREFERENCES`: the
   model doesn't choose like vs skip, so that text only moves the score
   indirectly, while the threshold moves it exactly.
6. Optionally: set `SWIPE_VOLUME_GUIDANCE` to calibrate how the mode's
   rubric maps onto the 0-100 range — it replaces the shared
   `DEFAULT_VOLUME_GUIDANCE`. Reserve this for a rubric whose scale
   genuinely differs from the generic one; `FIT_SCORE_MIN` is the usual
   lever.
7. Optionally: set `MAX_LIKES_PER_SESSION` / `MAX_PROFILES_PER_SESSION`
   to give this mode its own caps.
8. Re-check the rubric's wording is in scoring terms ("score low",
   "clears the bar") rather than swipe terms — see Phase 4 step 5.
9. Update `ACTIVE_MODE` in `config.py` to their new mode's `NAME`.

A mode that omits `FIT_SCORE_MIN` / `SWIPE_VOLUME_GUIDANCE` / the caps
inherits the `config.py` defaults (or the `.env` value, which is the
baseline those defaults resolve to) — `_apply_mode()` resets them each
call, so `--mode X` can't inherit the last mode's tuning.

### Phase 5a — Profile health check (recommended before going live)

`scan_self.py` was written against Hinge's self-profile screens and has
not been converted to Bumble's yet, so don't promise it works. If the
user wants a profile review, run it and see — if it can't find the
screens, say so rather than inventing a report.

### Phase 5 — First live run

1. Leave `MAX_LIKES_PER_SESSION = 20` (default) and `DRY_RUN = False`
   (default).
2. Have the user start the loop: `python run.py` (with the Bumble feed
   open). Watch the printed decisions live. `run.py` is a thin wrapper
   over `main.py` that also reports failures raised before the loop
   starts; `python main.py` works the same for a live session.
3. Stop with Ctrl-C if anything looks wrong — a like that should've
   been a skip, a skip that should've been a like, etc.
4. Review the frames and decisions under `debug/` (`debug/liked/` and
   `debug/skipped/`, one folder per profile, plus the JSONL log). Walk
   through the decisions together.
5. **Iterate on `PREFERENCES`** based on what they see — and on
   `FIT_SCORE_MIN` if the complaint is volume rather than taste. The
   printed `avg fit N/100` and each profile's `fit_score` in `debug/` /
   the JSONL log say whether the rubric is scoring well and only the
   threshold is off (scores cluster above or below the line) or whether
   the rubric itself is wrong (scores look random relative to the
   profiles). On free tier the user has to wait for the daily swipe
   allotment to reset before a meaningful next batch; with Bumble+ they
   can re-run immediately.
6. Once dialed in: if the user has Bumble+, raise
   `MAX_LIKES_PER_SESSION` to 30–50 and consider running multiple
   sessions across the day. If they don't, leave it at 20 and treat one
   session as the day's budget.

Dry-run guidance by tier (see Hard Constraints):
- Free Bumble first run: yes, set `DRY_RUN = True` so the daily
  allotment survives rubric iteration. Flip back to False once the
  rubric looks dialed.
- Bumble+: stay live with a small cap, Ctrl-C and iterate. No dry-run
  needed.

## Architecture orientation (for when the user asks "where does X live")

- `main.py` — loop runner; capture → judge → act.
- `run.py` — cron entry point and outer crash net: imports `main` inside
  a `try` so an import-time failure still reaches Discord, then passes
  `main()`'s exit code through. `main()` returns 1 on abort, 0 on a
  clean run, so `cron.log`'s `Done (exit N)` line distinguishes them.
  Arguments pass through untouched, which is how the cron wrapper's
  `--mode carlos` still reaches `main()`'s argparse.
- `report.py` — Discord webhook posts. Error and crash posts @mention
  the user ID in `DISCORD_MENTION_USER_ID`; the mention has to be in the
  top-level `content`, since Discord ignores mentions rendered inside an
  embed. With the channel set to "Only @mentions", routine posts stay
  silent and failures ping — so a user asking "why didn't I get
  notified?" usually has a channel-level notification setting to check,
  not a bug here.
- `judge_common.py` — backend-agnostic system prompt, tool schema,
  `Decision` dataclass, `apply_fit_threshold()` (the one place like/skip is
  decided), `load_backend()` dispatcher, and the fatal/network error
  classifiers.
- `judge.py` — Anthropic backend.
- `judge_gemini.py` — Gemini backend.
- `judge_deepseek.py` — DeepSeek backend (OpenAI-compatible REST).
- `judge_ollama.py` — Ollama Cloud / local backend.
- `config.py` — single source of truth for COORDS, DRY_RUN,
  ACTIVE_MODE, JUDGE_BACKEND. Mode files write into here via
  `_apply_mode()`.
- Where debug output lands is `config.DEBUG_DIR` — `debug/` under the
  repo by default, but overridable from `.env` (`DEBUG_DIR=...`) because
  a full corpus runs to gigabytes. Read the value rather than assuming
  `./debug` when you go looking for frames; on this machine it points at
  a separate disk.
- `modes/` — rubric files. Each exports `NAME`, `PREFERENCES`, and
  optional `AGE_MIN/MAX`, `FIT_SCORE_MIN`, `MAX_LIKES_PER_SESSION`,
  `MAX_PROFILES_PER_SESSION`, `SWIPE_VOLUME_GUIDANCE`.
- `adb.py` — emulator I/O: screenshot, tap, swipe, type, deadline on
  every call.
- `metrics.py` — JSONL session logging and per-backend cost estimates.
- `scan_self.py` — the one Hinge-era tool left in the tree: captures the
  user's own profile and asks Claude for improvement suggestions. Not
  wired into the swipe loop and not converted to Bumble's screens, so it
  may not find its way around the app — verify before promising a report.

## Self-correcting calibration drift

The shipped `config.COORDS` are tuned for a 720×1600 device against a
specific Bumble build. If the user's setup is the same, the gestures
land correctly. If not, you'll see symptoms like:

- A swipe that should advance a profile does nothing.
- A swipe that should skip lands on a like (or vice versa) because the
  gesture started outside the card.
- A run that keeps force-skipping: `main.py`'s duplicate detection
  fires when frame 0 is unchanged, which usually means the action
  gesture didn't register at all.
- A run that prints `DIALOG DETECTED` and restarts the app on repeat:
  the judge is seeing a popup rather than a profile. That's the
  guard working, not a calibration problem — but if it escalates to
  `TIER 3` and aborts, Bumble has changed its upsell/prompt screens
  enough that a back press no longer clears them. The run pings Discord
  and exits 1 on that path; look at the screenshot it saved under
  `<DEBUG_DIR>/errors/` and at `_recover_from_dialog()` in `main.py`.

When this happens, don't just shrug — you can fix it in-session.

### Recipe

1. **Confirm by screenshot**: capture before-state, attempt the
   gesture, capture after-state, visually compare. Don't trust the
   gesture; trust the screenshot pair.

   ```bash
   adb exec-out screencap -p > /tmp/before.png
   adb shell input swipe <x1> <y1> <x2> <y2> <duration_ms>
   sleep 1.2
   adb exec-out screencap -p > /tmp/after.png
   ```

2. **Detect the element**: load the before-state PNG and locate the
   real element center with PIL + numpy + scipy:

   ```python
   from PIL import Image
   import numpy as np
   from scipy.ndimage import label, find_objects

   img = np.array(Image.open("/tmp/before.png").convert("RGB"))
   # Look in the region where the element should be (narrow the
   # search to avoid false positives).
   region = img[y_lo:y_hi, x_lo:x_hi]
   # Match by color: Bumble's action row is a white X (skip) and a
   # yellow heart (like) on a dark card, bottom of the screen.
   mask = region.mean(axis=2) < 100
   labeled, _ = label(mask)
   for i, sl in enumerate(find_objects(labeled), 1):
       # Filter by size — most tap targets are 40-150 px square.
       ...
   ```

3. **Verify**: repeat the gesture with the new coord, capture, confirm
   the expected screen appeared. If it did, the coord is right.

4. **Patch `config.py`** with the corrected value. Show the user the
   diff before writing.

### Patterns by element type

- **Swipe gestures**: what actually needs to be right. The x values
  must straddle the card (the shipped values use 20% and 80% of a
  720px width) and the y must be inside the card, well clear of the
  status bar and the action row. `adb.py` re-randomizes the scroll
  gesture's x per swipe within a 15% edge guard, so keep start and end
  x clear of the screen edges or the back-gesture strip intercepts
  them.
- **Scroll gesture**: only the y values in `COORDS["scroll_from"]` /
  `["scroll_to"]` are read; the live x is drawn per gesture.
- **Bottom-nav icons**: `COORDS["nav_swipe"]` is the center slot,
  used once at startup to land on the feed. If Bumble's nav moves,
  re-detect with a brightness peak per column across that band.
- **Match popup dismiss**: `COORDS["match_dismiss"]` is the top-left X
  on the "What a match!" screen, tapped after every like whether or not
  a match occurred (a stray tap on a non-match screen is harmless).

### Things NOT to auto-patch

- Anything that requires multiple drags, or that lives behind an
  in-app panel rather than on the profile card. The loop only needs
  the swipe/scroll coords; a slider or a picker isn't worth automating
  and isn't worth guessing at. Have the user set it by hand in the app.
- Anything that needs the user to confirm a screen-state change. Walk
  the user through it; don't guess.

## Things to push back on

- Helping a user run this against their primary account.
- Removing the ToS warning, or setting `MAX_LIKES_PER_SESSION` to a
  very high number (>50) on a free account — they'll burn quota and
  may trip throttling without realizing why.
- Writing taste-based filtering rules the user didn't explicitly ask
  for (e.g., don't infer body-type or ethnicity preferences from
  vague prompts — ask what they actually want).
- Detection-evasion or fingerprint-spoofing requests.
- Scaling beyond one account ("run this on my friends' accounts too",
  "rotate through 5 logins") — refuse; this is the mass-targeting
  failure mode.

## Things to be proactive about

- If `config.COORDS` still looks like the shipped 720×1600 values when
  the user is about to run on a different device, flag it — the bot
  will tap into the void.
- If `MAX_LIKES_PER_SESSION` is set far above what the user's tier
  allows, flag that the excess won't fire (a free account runs out of
  daily swipes first) or may trip Bumble's soft-throttle.
- If the user's `PREFERENCES` rubric has internal contradictions (e.g.
  default LIKE + a long list of skip rules), point that out.
- If a session log shows a clear pattern of bad decisions, suggest
  the rubric change before they keep running.
