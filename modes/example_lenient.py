"""Lenient Bumble mode — score generously, lean toward liking."""

NAME = "example_lenient"
DESCRIPTION = "Score generously; only clearly bad profiles fall below the bar"

AGE_MIN = None
AGE_MAX = None

# The pickiness dial. The judge scores each profile 0-100 and the harness
# likes iff fit_score >= FIT_SCORE_MIN — the mode file can't make the model
# swipe right more, it can only move this number. The shared default is 50;
# this example is meant to be generous, so it sits lower. Pair it against
# example_strict (65) to see the range.
FIT_SCORE_MIN = 40

PREFERENCES = """
You are evaluating Bumble profiles for the user.

## Hard skips (score these below 20)
- Empty / low-effort profiles (1 photo, no bio)
- Profiles with obvious dealbreakers visible
- Profiles where age is clearly way off

## Green flags (score these high)
- Active lifestyle
- Well-filled profile with personality
- Shared interests visible

## Decision guidance
- Be generous with scores — anything you could potentially date clears 40
- When in doubt, round up rather than down
- Don't overthink — this is volume swiping, not perfectionism
"""
