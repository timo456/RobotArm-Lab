"""Homogeneous-transform FK and bounded numerical SE(3) inverse kinematics."""

from dataclasses import dataclass
from time import perf_counter

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from .config import Config
from .model import AXES, HOME, LOWER, ORIGINS, TOOL, UPPER, Array, CommandError, Pose, joints


def axis_rotation(axis: Array, angle: float) -> Array:
    x, y, z = axis
    skew = np.array([[0, -z, y], [z, 0, -x], [-y, x, 0]])
    return np.eye(3) + np.sin(angle) * skew + (1 - np.cos(angle)) * (skew @ skew)


def _fk(q: Array) -> Pose:
    r, p = np.eye(3), np.zeros(3)
    for origin, axis, angle in zip(ORIGINS, AXES, q, strict=True):
        p = p + r @ origin
        r = r @ axis_rotation(axis, angle)
    return Pose(p + r @ TOOL, r)


def fk(q: object) -> Pose:
    """World-frame TCP, computed without PyBullet or URDF-derived transforms."""
    return _fk(joints(q))


def pose_error(actual: Pose, target: Pose) -> tuple[float, float]:
    return (
        float(np.linalg.norm(actual.position - target.position)),
        float(Rotation.from_matrix(target.rotation @ actual.rotation.T).magnitude()),
    )


@dataclass(frozen=True)
class IKResult:
    q: Array
    position_error: float
    orientation_error: float
    elapsed_ms: float
    attempts: int


def solve_ik(target: Pose, seed: object, config: Config) -> IKResult:
    """Deterministic multi-start solve; optimizer success alone never implies acceptance."""
    start = perf_counter()
    initial = joints(seed)
    if np.linalg.norm(target.position - ORIGINS[0]) > 1.09:
        raise CommandError("Unreachable target: outside conservative reach bound")

    def residual(q: Array) -> Array:
        actual = _fk(q)
        # 0.3 m/rad balances translational and rotational residuals.
        return np.r_[
            actual.position - target.position,
            0.3 * Rotation.from_matrix(target.rotation @ actual.rotation.T).as_rotvec(),
        ]

    rng = np.random.default_rng(618)
    bearing = float(np.arctan2(target.position[1], target.position[0]))
    # Cover elbow and wrist branches geometrically before using random restarts.
    branches = [
        np.array([bearing, -0.5 * elbow, elbow, 0.0, wrist, 0.0])
        for elbow in (-1.0, 1.0)
        for wrist in (-0.7, 0.7)
    ]
    seeds = [initial, HOME, *branches] + [
        rng.uniform(LOWER, UPPER) for _ in range(max(0, config.ik_restarts - 6))
    ]
    best = (float("inf"), float("inf"))
    for attempt, guess in enumerate(seeds[: config.ik_restarts], 1):
        result = least_squares(
            residual,
            np.clip(guess, LOWER + 1e-10, UPPER - 1e-10),
            bounds=(LOWER, UPPER),
            max_nfev=180,
            ftol=1e-10,
            xtol=1e-10,
            gtol=1e-10,
        )
        q = joints(result.x)
        pe, re = pose_error(fk(q), target)
        best = min(best, (pe, re))
        if pe <= config.ik_position_tolerance and re <= config.ik_orientation_tolerance:
            q.setflags(write=False)
            return IKResult(q, pe, re, (perf_counter() - start) * 1000, attempt)
    raise CommandError(
        f"IK rejected after {config.ik_restarts} attempts; "
        f"best position={best[0]:.6g} m, orientation={best[1]:.6g} rad"
    )
