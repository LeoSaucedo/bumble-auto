<p align="center">
  <strong>BUMBLEAUTO</strong>
</p>

<p align="center">
  <strong>Automated Bumble swiping powered by vision LLMs.</strong><br/>
  Reads dating profiles through screen captures, judges them against your preferences, and swipes right or left automatically.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-FF4FD8.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-FF4FD8?logo=python&logoColor=white">
  <img alt="Judge: Gemini, Claude, or DeepSeek" src="https://img.shields.io/badge/judge-Gemini%20%C2%B7%20Claude%20%C2%B7%20DeepSeek-FF4FD8">
  <img alt="Drives Android via ADB" src="https://img.shields.io/badge/device-Android%20%C2%B7%20ADB-FF4FD8">
  <a href="#-read-this-first"><img alt="Violates Bumble ToS — use at your own risk" src="https://img.shields.io/badge/%E2%9A%A0-violates%20Bumble%20ToS-red"></a>
</p>

<p align="center">
  <a href="#-read-this-first">Read this first</a> ·
  <a href="#quickstart">Quickstart</a> ·
  <a href="#backends">Backends</a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="#differences-from-hinge-auto">Differences from HingeAuto</a> ·
  <a href="LICENSE">License</a>
</p>

---

BumbleAuto is what you get when you point a vision-LLM at a phone screen and let
it swipe for you. An Android device runs a real Bumble install; this repo drives
it over ADB, scoring every profile against a rubric **you** write and acting on
the verdict — swipe left (skip), or swipe right (like).

The judge never picks like vs skip itself. It returns a **fit score** (0–100)
plus the single `dominant_factor` that drove it, and the harness decides:
like iff `fit_score >= FIT_SCORE_MIN`. Keeping the threshold out of the prompt
means the model can't game a number it never sees, and re-tuning how picky the
bot is becomes a config edit instead of a prompt rewrite — raise `FIT_SCORE_MIN`
for fewer, better likes; lower it for volume.

Bumble's core flow differs from Hinge — there's no "send message with like"
feature. The bot simply swipes right on profiles worth matching, and the rest
is up to you.

## ⚠ Read this first

**This project automates Bumble, which violates Bumble's Terms of Service.**
Real risk of account ban with no appeal. Treat this as an educational toy
for a single throwaway account, not a dating strategy.

- **One account only.**
- **Get Bumble+ or Bumble Premium** if you're going to use this seriously.
  Free-tier Bumble has limited daily swipes.
- **No warranty. No support.** Your account, your problem.

## What it does

Drives an Android device running Bumble through ADB. For each profile it
scrolls through all content (photos + prompts), captures screenshots, asks a
vision LLM to score it against your rubric, and swipes right (like) or left
(skip). No messaging — Bumble requires mutual matching and the woman messages
first.

Two guards keep the loop from spending swipes on the wrong things:

- **The fit-score gate.** The model's verdict is a number, not a decision. A
  runtime config read, `FIT_SCORE_MIN`, is what turns it into like or skip.
- **Dialog detection.** Popups, upsells, permission prompts and other
  non-profile screens get reported as `NOT_A_PROFILE` instead of being scored
  as a person. The loop then recovers — back press, then app restart, then a
  Discord alert and a clean stop — rather than swiping at a dialogue box.

## Quickstart

### 1. Set up Android device with ADB

Enable **Developer options** → **USB debugging** on an Android phone with
Bumble installed. Connect via USB or ADB over TCP/IP:

```bash
adb tcpip 5555
adb connect <phone-ip>:5555
adb devices  # confirm device
```

### 2. Install dependencies

```bash
git clone https://github.com/LeoSaucedo/bumble-auto.git
cd bumble-auto
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure `.env`

```bash
cp .env.example .env
```

Add your API key for the desired backend (see [Backends](#backends)).

### 4. Run

```bash
source .venv/bin/activate
python main.py
```

Each profile scrolls through screenshots, the judge scores it, the harness
turns that score into like/skip, and the bot swipes accordingly. Running totals
print after each profile, including the session's average fit score.

## Backends

The judge pipeline supports four interchangeable backends set via
`JUDGE_BACKEND` in `config.py`. All share the same system prompt, schema, and
`Decision` shape.

### `"deepseek"` (cheap, OpenAI-compatible)

Uses DeepSeek's OpenAI-compatible API (`deepseek-flash`, vision-capable)
with a forced tool call. Measured **~$0.0015–$0.003 per profile** on a
7-frame profile (off-peak rates are half the peak ones) — roughly a tenth
of the Anthropic backend's cost, and cheaper than the mid-tier Gemini
flash models.

Setup: `DEEPSEEK_API_KEY` in `.env`. Override model via `DEEPSEEK_MODEL`
(only `deepseek-flash` has vision — `deepseek-v4-pro` does not).
`DEEPSEEK_THINKING=true` trades the guaranteed tool call for extra
reasoning; see the header of `judge_deepseek.py` for the tradeoff.

### `"gemini"` (cheap)

Uses Google Gemini. **$0.00025–$0.0015 per profile** on Flash Lite.

Setup: `GEMINI_API_KEY` in `.env`. Override model via `GEMINI_MODEL`.
Current flash options (input/output per 1M tokens, Sept 2026):
`gemini-3.5-flash-lite` $0.30/$2.50 (default), `gemini-3.1-flash-lite`
$0.25/$1.50, `gemini-3.6-flash` / `3.7-flash` / `3.8-flash` $0.75/$3.75
(those three double on 2027-01-01), `gemini-3.5-flash` $1.50/$9.00.

### `"anthropic"` (best quality)

Uses Claude with vision + forced tool calling. Best quality decisions.
Roughly **$0.02–$0.05 per profile**.

Setup: `ANTHROPIC_API_KEY` in `.env`.

### `"ollama"` (free, local or cloud)

Uses a vision model on local Ollama or Ollama Cloud. Lower quality
structured output, but no per-token cost.

Setup: `OLLAMA_MODEL` / `OLLAMA_HOST` in `config.py`, plus
`OLLAMA_API_KEY` for Ollama Cloud. See `requirements-ollama.txt`.

## Architecture

```
ADB capture    →  frame stitching  →  LLM judge         →  swipe
   adb.py          config / main       judge_deepseek.py     main.py / adb.py
                                       judge_gemini.py
                                       judge.py
                                       judge_ollama.py
                                       judge_common.py
```

### Module breakdown

| Module | Role |
|---|---|
| **`adb.py`** | Wraps the `adb` CLI: screenshot, tap, swipe, type. |
| **`main.py`** | The orchestration loop. For each profile: scroll through content, capture frames, run through judge, then swipe right or left. |
| **`judge_common.py`** | Backend-agnostic pipeline: system prompt template, JSON tool schema, `Decision` dataclass, `apply_fit_threshold()` (the one place like/skip gets decided), and `load_backend()` dispatcher. |
| **`judge.py`** | Anthropic Claude backend — vision + forced tool call. |
| **`judge_deepseek.py`** | DeepSeek backend — vision + forced tool call (OpenAI-compatible REST, no SDK). |
| **`judge_gemini.py`** | Google Gemini backend — vision + function declaration. |
| **`judge_ollama.py`** | Ollama backend — local or Ollama Cloud vision model. |
| **`metrics.py`** | Per-profile cost tracking and JSONL logging. |
| **`report.py`** | Discord webhook reporting with batched attachments. |
| **`config.py`** | All settings with `.env` override support. |
| **`run_random_window.sh`** | Cron wrapper with random jitter for session randomization. |

### Session flow

1. ADB captures profile screenshots (photos + prompts)
2. Frames + system prompt sent to the active judge backend
3. Judge returns a structured `Decision`: `fit_score` (0–100),
   `dominant_factor`, confidence, reasoning — or `NOT_A_PROFILE` if a popup
   or other non-profile screen blocked the view
4. Harness applies the gate: like iff `fit_score >= FIT_SCORE_MIN`
5. A `NOT_A_PROFILE` verdict instead runs dialog recovery (back press →
   app restart → alert and stop) and returns to step 1 without spending a swipe
6. Swipe right (like) or left (skip) via ADB swipe gesture
7. Match popup dismissed if present
8. Metrics logged, Discord stats posted
9. Loops until like cap hit

### Tuning pickiness

`FIT_SCORE_MIN` defaults to 50 and can be set in `.env` (global default) or in
a mode file (per-mode). `example_lenient` ships at 40, `example_strict` at 65.

Judge `fit_score` alongside `FIT_SCORE_MIN` when a run doesn't feel right. The
`avg fit N/100` line printed after every profile tells you which knob to turn:

- **Scores cluster just under the threshold** → the rubric agrees with you and
  only the threshold is off. Lower `FIT_SCORE_MIN`.
- **Scores look random relative to the profiles** → the rubric needs work, not
  the threshold. A threshold change would just move the same bad cut.

## Differences from HingeAuto

BumbleAuto is adapted from [HingeAuto](https://github.com/LeoSaucedo/hinge-auto)
with fundamental differences due to Bumble's design:

| Aspect | HingeAuto | BumbleAuto |
|---|---|---|
| **Action** | Tap heart, type message, tap Send Like | Swipe right (gesture) |
| **Messaging** | Sends opener with like | No message on like (Bumble requires match + woman messages first) |
| **Match popup** | Inline compose card | Separate "What a match!" screen to dismiss |
| **Scrolling** | Top-to-bottom, then scroll back | Similar, but Bumble profile layout differs |
| **UID** | Button taps | Swipe gestures |
| **Volume** | Lower (8-16 likes/session) | Higher (up to 20 likes/session) |

## License

MIT. See [`LICENSE`](LICENSE).

## Credits

Infrastructure (ADB control, vision pipeline, config system, webhook reporting)
adapted from [hinge-auto](https://github.com/TerraByte-Dev/hinge-auto) by
TerraByte Solutions LLC. BumbleAuto is a ground-up adaptation for Bumble's
swipe-only mechanics and higher-volume patterns.

Built with ❤️ by [LeoSaucedo](https://github.com/LeoSaucedo)
