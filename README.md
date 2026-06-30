# BumbleAuto

**Automated Bumble swiping powered by Gemini / Claude vision.**

Reads dating profiles through screen captures, judges them against your preferences, and swipes right or left automatically.

## How it works

1. Runs on a real Android phone connected via ADB over Tailscale
2. Opens Bumble and scrolls through each profile, capturing screenshots
3. Sends frames to a vision model (Gemini 3.1 Flash Lite by default) for judgment
4. Taps the heart (like) or X (skip) at the bottom of the profile
5. Repeats until the daily cap or profile limit is hit
6. Posts a summary to Discord with stats + profile photos

## Getting Started

```bash
# Clone & install
git clone https://github.com/LeoSaucedo/bumble-auto
cd bumble-auto
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your settings
```

### Requirements

- Android phone with ADB enabled (USB debugging + TCP/IP mode)
- Tailscale on both phone and server for remote ADB
- A Gemini API key (cheapest option) or Anthropic API key
- Bumble+ subscription (for unlimited swipes)

### Configuration

All settings live in `config.py` but can be overridden via `.env`:

```env
# Required
GEMINI_API_KEY=your_key_here

# Override any config variable
JUDGE_BACKEND=gemini
MAX_LIKES_PER_SESSION=20
```

### Running

```bash
# Quick run
python main.py --mode example_lenient

# With cron (9am-9pm, randomized intervals)
# Add to crontab:
# 20 9-21 * * * /path/to/bumble-auto/run_random_window.sh
```

## Credits

Heavily inspired by [hinge-auto](https://github.com/LeoSaucedo/hinge-auto) — the original Hinge automation project that this was forked from. The infrastructure (ADB control, vision pipeline, env-based config, webhook reporting) carries over, but BumbleAuto is a ground-up adaptation with swipe-only mechanics, higher-volume patterns, and a simplified judging pipeline.

Built with ❤️ by [LeoSaucedo](https://github.com/LeoSaucedo)
