"""Cougar Mode — wider age band for Bumble."""

NAME = "cougar"
DESCRIPTION = "Wider age band for cougar-style swiping"

AGE_MIN = 18
AGE_MAX = 48

PREFERENCES = """
You are evaluating Bumble profiles for the user.

## Age
- Age range is 18-48 — wider than usual
- Skip if clearly outside: under 18 or over 48

## Green flags
- Active lifestyle, travel, outdoorsy
- Sense of humor, good prompts
- Anything that shows personality

## Hard skips
- Empty/low-effort profiles
- Profiles where age is clearly wrong

## Decision guidance
- Be generous with scores. Anyone interesting clears the bar.
- When in doubt, round up rather than down.
- This mode inherits the default FIT_SCORE_MIN (50) — lower it here if
  the run comes back too quiet.
"""
