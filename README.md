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
  <img alt="Judge: Gemini, or Claude" src="https://img.shields.io/badge/judge-Gemini%20%C2%B7%20Claude-FF4FD8">
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
it over ADB, judging every profile against a rubric **you** write and acting on
the verdict — swipe left (skip), or swipe right (like).

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
vision LLM to judge against your rubric, and swipes right (like) or left (skip).
No messaging — Bumble requires mutual matching and the woman messaging first.

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

Each profile scrolls through screenshots, the judge decides like/skip, and the
bot swipes accordingly. Running totals print after each profile.

## Backends

The judge pipeline supports two interchangeable backends set via
`JUDGE_BACKEND` in `config.py`. All share the same system prompt, schema, and
`Decision` shape.

### `"gemini"` (default, cheap)

Uses Google Gemini. **$0.00025–$0.0015 per profile** on Flash Lite.

Setup: `GEMINI_API_KEY` in `.env`. Override model via `GEMINI_MODEL`.

### `"anthropic"` (best quality)

Uses Claude with vision + forced tool calling. Best quality decisions.
Roughly **$0.02–$0.05 per profile**.

Setup: `ANTHROPIC_API_KEY` in `.env`.

## Architecture

```
ADB capture    →  frame stitching  →  LLM judge        →  swipe
   adb.py          config / main       judge_gemini.py      main.py / adb.py
                                       judge.py
                                       vision.py
                                       judge_common.py
```

### Module breakdown

| Module | Role |
|---|---|
| **`adb.py`** | Wraps the `adb` CLI: screenshot, tap, swipe, type. |
| **`main.py`** | The orchestration loop. For each profile: scroll through content, capture frames, run through judge, then swipe right or left. |
| **`judge_common.py`** | Backend-agnostic pipeline: system prompt template, JSON tool schema, `Decision` dataclass, and `load_backend()` dispatcher. |
| **`judge.py`** | Anthropic Claude backend — vision + forced tool call. |
| **`judge_gemini.py`** | Google Gemini backend — vision + function declaration. |
| **`vision.py`** | Finds UI elements: heart icon (like), X icon (skip), match-dismiss popup. |
| **`metrics.py`** | Per-profile cost tracking and JSONL logging. |
| **`report.py`** | Discord webhook reporting with batched attachments. |
| **`config.py`** | All settings with `.env` override support. |
| **`run_random_window.sh`** | Cron wrapper with random jitter for session randomization. |

### Session flow

1. ADB captures profile screenshots (photos + prompts)
2. Frames + system prompt sent to the active judge backend
3. Judge returns structured `Decision` (like/skip, confidence, reasoning)
4. Swipe right (like) or left (skip) via ADB swipe gesture
5. Match popup dismissed if present
6. Metrics logged, Discord stats posted
7. Loops until like cap hit

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
