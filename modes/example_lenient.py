"""Lenient Bumble mode — swipe right generously on decent profiles."""

NAME = "example_lenient"
DESCRIPTION = "Swipe right on most profiles that don't have obvious dealbreakers"

AGE_MIN = None
AGE_MAX = None

PREFERENCES = """
You are evaluating Bumble profiles for the user.

## Hard skips (swipe left on all of these)
- Empty / low-effort profiles (1 photo, no bio)
- Profiles with obvious dealbreakers visible
- Profiles where age is clearly way off

## Green flags (swipe right)
- Active lifestyle
- Well-filled profile with personality
- Shared interests visible

## Decision guidance
- Be generous — swipe right on anyone you could potentially date
- When in doubt, swipe right
- Don't overthink — this is volume swiping, not perfectionism
"""
