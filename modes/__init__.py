"""Mode bundles for BumbleAuto.

Each mode is a Python module under `modes/` exporting at minimum `NAME` and
`PREFERENCES`. Optional: `AGE_MIN`, `AGE_MAX`, `MAX_LIKES_PER_SESSION`,
`MAX_PROFILES_PER_SESSION`.

`config.py` resolves the active mode at import time via `config._apply_mode()`
and writes the mode's constants into `config`'s module globals, so callers
keep using `config.PREFERENCES` etc. unchanged.
"""

import importlib
from types import ModuleType


def load(name: str) -> ModuleType:
    try:
        return importlib.import_module(f"modes.{name}")
    except ModuleNotFoundError as e:
        raise KeyError(
            f"Unknown mode {name!r}. Create modes/{name}.py to define it."
        ) from e
