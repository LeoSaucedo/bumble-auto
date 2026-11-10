"""Strict Bumble mode — selective, high threshold."""

NAME = "example_strict"
DESCRIPTION = "Be selective — only genuinely compatible profiles clear the bar"

AGE_MIN = 22
AGE_MAX = 35

# The pickiness dial. The judge scores each profile 0-100 and the harness
# likes iff fit_score >= FIT_SCORE_MIN — the mode file can't make the model
# swipe left more, it can only raise this number. The shared default is 50;
# this example is meant to be strict, so it sits above. Pair it against
# example_lenient (40) to see the range.
FIT_SCORE_MIN = 65

PREFERENCES = """
You are evaluating Bumble profiles for the user. Be selective.

## Hard skips (score these very low)
- No or minimal bio
- Only selfies/1 photo
- Obvious dealbreaker (smoker, has kids, etc.)
- Height or age clearly outside preference

## Green flags (score these high)
- Active lifestyle
- Creative or artistic pursuits
- Genuine thought in prompts/bio
- Shared interests

## Decision guidance
- This is a strict mode — reserve 70+ for profiles that genuinely
  stand out as compatible
- When in doubt, score below the bar rather than above it
"""
