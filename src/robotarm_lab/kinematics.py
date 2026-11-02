"""Homogeneous-transform FK and bounded numerical SE(3) inverse kinematics."""

import warnings
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
    diagnostics: tuple[dict, ...] = ()


class IKFailure(CommandError):
    def __init__(self, message: str, diagnostics: tuple[dict, ...] = ()) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics


def geometric_seeds(target: Pose, seed: Array, config: Config) -> list[Array]:
    """RAL-6 spherical wrist: two shoulder, two elbow and two XYX wrist branches.

    J4/J6 rotate about their local X axes, so their X offsets lie on those axes.
    The wrist center is TCP - (0.10+0.12)*R[:,0]; upper/forearm lengths are 0.32/0.38.
    These seeds are never trusted until FK residual and joint-bound validation pass.
    """
    center = target.position - (ORIGINS[5, 0] + TOOL[0]) * target.rotation[:, 0]
    shoulder = ORIGINS[0] + ORIGINS[1]
    offset = center - shoulder
    a, b = ORIGINS[2, 0], ORIGINS[3, 0] + ORIGINS[4, 0]
    distance = float(np.linalg.norm(offset))
    tolerance = config.ik_position_tolerance + 1e-7
    if distance > a + b + tolerance or distance < abs(a - b) - tolerance:
        raise IKFailure("Unreachable wrist center: outside two-link reach annulus")
    cosine = np.clip((distance**2 - a * a - b * b) / (2 * a * b), -1.0, 1.0)
    elbow = float(np.arccos(cosine))
    bearing = float(np.arctan2(offset[1], offset[0]))
    # On the base axis yaw is underdetermined. Preserve the caller's yaw as one branch.
    yaws = [seed[0], 0.0] if np.hypot(*offset[:2]) < 1e-9 else [bearing, bearing + np.pi]
    candidates = []

    def wrap(angle: float) -> float:
        return float((angle + np.pi) % (2 * np.pi) - np.pi)

    for yaw in yaws:
        yaw = wrap(yaw)
        radial = offset[0] * np.cos(yaw) + offset[1] * np.sin(yaw)
        down = -offset[2]
        for q3 in (elbow, -elbow):
            q2 = wrap(
                float(np.arctan2(down, radial) - np.arctan2(b * np.sin(q3), a + b * np.cos(q3)))
            )
            arm_rotation = axis_rotation(AXES[0], yaw) @ axis_rotation(AXES[1], q2 + q3)
            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore", message="Gimbal lock detected.*", category=UserWarning
                )
                q4, q5, q6 = Rotation.from_matrix(arm_rotation.T @ target.rotation).as_euler("XYX")
            for wrist in [(q4, q5, q6), (q4 + np.pi, -q5, q6 + np.pi)]:
                candidate = np.array([yaw, q2, q3, *[wrap(float(v)) for v in wrist]])
                # Refine bound-adjacent simulator roundoff after clipping; always validate.
                candidates.append(np.clip(candidate, LOWER, UPPER))
    return sorted(
        candidates,
        key=lambda q: (
            np.linalg.norm(q - seed)
            if np.linalg.norm(_fk(q).position - target.position) < tolerance
            else 100 + np.linalg.norm(_fk(q).position - target.position)
        ),
    )


def solve_ik(target: Pose, seed: object, config: Config) -> IKResult:
    """Deterministic multi-start solve; optimizer success alone never implies acceptance."""
    start = perf_counter()
    initial = joints(seed)
    if np.linalg.norm(target.position - ORIGINS[0]) > 1.09:
        raise IKFailure("Unreachable target: outside conservative reach bound")
    analytic = geometric_seeds(target, initial, config)

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
    seeds = [initial, *analytic, HOME, *branches] + [
        rng.uniform(LOWER, UPPER) for _ in range(config.ik_restarts)
    ]
    unique = []
    for guess in seeds:
        if not any(np.allclose(guess, q, atol=1e-10, rtol=0) for q in unique):
            unique.append(guess)
    best = (float("inf"), float("inf"))
    diagnostics = []
    for attempt, guess in enumerate(unique[: config.ik_restarts], 1):
        q = np.clip(guess, LOWER, UPPER)
        pe, re = pose_error(fk(q), target)
        if pe <= config.ik_position_tolerance and re <= config.ik_orientation_tolerance:
            q.setflags(write=False)
            diagnostics.append(
                dict(
                    attempt=attempt,
                    method="validated_seed",
                    nfev=0,
                    position_error=pe,
                    orientation_error=re,
                )
            )
            return IKResult(q, pe, re, (perf_counter() - start) * 1000, attempt, tuple(diagnostics))
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
        diagnostics.append(
            dict(
                attempt=attempt,
                method="bounded_least_squares",
                nfev=int(result.nfev),
                status=int(result.status),
                position_error=pe,
                orientation_error=re,
                active_bounds=int(np.count_nonzero(result.active_mask)),
            )
        )
        if pe <= config.ik_position_tolerance and re <= config.ik_orientation_tolerance:
            q.setflags(write=False)
            return IKResult(q, pe, re, (perf_counter() - start) * 1000, attempt, tuple(diagnostics))
    raise IKFailure(
        f"IK rejected after {config.ik_restarts} attempts; "
        f"best position={best[0]:.6g} m, orientation={best[1]:.6g} rad",
        tuple(diagnostics),
    )
