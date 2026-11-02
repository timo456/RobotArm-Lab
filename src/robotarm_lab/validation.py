"""Scalar and resource contracts shared by public entry points."""

from numbers import Real

import numpy as np

from .model import CommandError

MIN_COLLISION_STEP = 1e-6
MAX_COLLISION_STEP = 0.02
MAX_COLLISION_SAMPLES = 10_000


def scalar(value: object, name: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Real):
        raise CommandError(f"{name} must be a finite real scalar")
    result = float(value)
    if not np.isfinite(result):
        raise CommandError(f"{name} must be a finite real scalar")
    return result


def collision_step(value: object) -> float:
    result = scalar(value, "Collision sampling step")
    if not MIN_COLLISION_STEP <= result <= MAX_COLLISION_STEP:
        raise CommandError(
            f"Collision sampling step must be in [{MIN_COLLISION_STEP}, {MAX_COLLISION_STEP}] rad"
        )
    return result
