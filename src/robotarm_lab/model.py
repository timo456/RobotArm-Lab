"""Original RAL-6 geometry; FK is intentionally independent of the URDF loader."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

Array = NDArray[np.float64]
ORIGINS = np.array(
    [[0, 0, 0.18], [0, 0, 0.16], [0.32, 0, 0], [0.28, 0, 0], [0.10, 0, 0], [0.10, 0, 0]],
    dtype=float,
)
AXES = np.array([[0, 0, 1], [0, 1, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0], [1, 0, 0]], dtype=float)
LOWER = np.deg2rad([-170, -110, -135, -180, -120, -180])
UPPER = np.deg2rad([170, 110, 135, 180, 120, 180])
HOME = np.array([0.0, -0.5, 1.0, 0.0, -0.5, 0.0])
TOOL = np.array([0.12, 0.0, 0.0])


class CommandError(ValueError):
    """A rejected command; callers must not execute it."""


def joints(value: object) -> Array:
    q = np.asarray(value, dtype=float)
    if q.shape != (6,) or not np.all(np.isfinite(q)):
        raise CommandError("Expected six finite joint angles in radians")
    if np.any(q < LOWER) or np.any(q > UPPER):
        raise CommandError("Joint limit exceeded")
    return q.copy()


@dataclass(frozen=True)
class Pose:
    position: Array
    rotation: Array

    def __post_init__(self) -> None:
        p = np.asarray(self.position, dtype=float).copy()
        r = np.asarray(self.rotation, dtype=float).copy()
        if p.shape != (3,) or r.shape != (3, 3):
            raise CommandError("Pose requires xyz position and a 3x3 rotation matrix")
        if not np.all(np.isfinite(p)) or not np.all(np.isfinite(r)):
            raise CommandError("Pose must be finite")
        if not np.allclose(r.T @ r, np.eye(3), atol=1e-7, rtol=0) or not np.isclose(
            np.linalg.det(r), 1, atol=1e-7, rtol=0
        ):
            raise CommandError("Rotation must belong to SO(3)")
        p.setflags(write=False)
        r.setflags(write=False)
        object.__setattr__(self, "position", p)
        object.__setattr__(self, "rotation", r)
