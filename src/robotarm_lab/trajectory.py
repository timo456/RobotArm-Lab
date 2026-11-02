"""Synchronized rest-to-rest quintics with analytic velocity/acceleration bounds."""

from dataclasses import dataclass

import numpy as np

from .config import Config
from .model import Array, CommandError, joints


@dataclass(frozen=True)
class Trajectory:
    start: Array
    goal: Array
    duration: float

    def __post_init__(self) -> None:
        if not np.isfinite(self.duration) or self.duration <= 0:
            raise CommandError("Trajectory duration must be finite and positive")
        for name in ("start", "goal"):
            value = joints(getattr(self, name))
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    def sample(self, time: float) -> tuple[Array, Array, Array]:
        if not np.isfinite(time):
            raise CommandError("Sample time must be finite")
        u = np.clip(time / self.duration, 0.0, 1.0)
        s = np.clip(10 * u**3 - 15 * u**4 + 6 * u**5, 0.0, 1.0)
        ds = (30 * u**2 - 60 * u**3 + 30 * u**4) / self.duration
        dds = (60 * u - 180 * u**2 + 120 * u**3) / self.duration**2
        delta = self.goal - self.start
        q = np.clip(
            self.start + delta * s,
            np.minimum(self.start, self.goal),
            np.maximum(self.start, self.goal),
        )
        if u == 0:
            q = self.start.copy()
        elif u == 1:
            q = self.goal.copy()
        return q, delta * ds, delta * dds

    def collision_samples(self, step: float) -> Array:
        if not np.isfinite(step) or step <= 0:
            raise CommandError("Collision sampling step must be finite and positive")
        # Joint-space line is identical to the quintic's geometric path.
        count = max(1, int(np.ceil(np.max(np.abs(self.goal - self.start)) / step)))
        return np.linspace(self.start, self.goal, count + 1)


def plan(start: object, goal: object, config: Config, duration: float | None = None) -> Trajectory:
    q0, q1 = joints(start), joints(goal)
    delta = np.abs(q1 - q0)
    # max s' = 15/8; max |s''| = 10*sqrt(3)/3, u in [0,1].
    minimum = max(
        config.control_dt,
        float(np.max(1.875 * delta / config.velocity)),
        float(np.max(np.sqrt((10 * np.sqrt(3) / 3) * delta / config.acceleration))),
    )
    if duration is not None and (not np.isfinite(duration) or duration < minimum):
        raise CommandError(f"Duration must be >= {minimum:.6f} seconds")
    q0.setflags(write=False)
    q1.setflags(write=False)
    return Trajectory(q0, q1, minimum if duration is None else float(duration))
