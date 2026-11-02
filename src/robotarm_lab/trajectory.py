"""Synchronized rest-to-rest quintics with analytic velocity/acceleration bounds."""

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np

from .config import Config
from .model import Array, CommandError, joints
from .validation import MAX_COLLISION_SAMPLES, collision_step, scalar


@dataclass(frozen=True)
class Trajectory:
    start: Array
    goal: Array
    duration: float

    def __post_init__(self) -> None:
        duration = scalar(self.duration, "Trajectory duration")
        if not 1e-6 <= duration <= 3600:
            raise CommandError("Trajectory duration must be within [1e-6,3600] seconds")
        object.__setattr__(self, "duration", duration)
        for name in ("start", "goal"):
            value = joints(getattr(self, name))
            value.setflags(write=False)
            object.__setattr__(self, name, value)

    def sample(self, time: float) -> tuple[Array, Array, Array]:
        time = scalar(time, "Sample time")
        if time <= 0:
            return self.start.copy(), np.zeros(6), np.zeros(6)
        if time >= self.duration:
            return self.goal.copy(), np.zeros(6), np.zeros(6)
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

    def collision_samples(self, step: float) -> Iterator[Array]:
        """Eager budget validation, lazy O(1) storage, never coarsen requested spacing."""
        step = collision_step(step)
        # Joint-space line is identical to the quintic's geometric path.
        delta = self.goal - self.start
        span = float(np.max(np.abs(delta)))
        # Compare before dividing: no overflow, giant integers or large allocations.
        if span > step * (MAX_COLLISION_SAMPLES - 1):
            raise CommandError(
                f"Collision sample budget exceeded ({MAX_COLLISION_SAMPLES}); "
                "command rejected without changing requested precision"
            )
        count = max(1, int(np.ceil(span / step)))
        if count + 1 > MAX_COLLISION_SAMPLES:
            raise CommandError("Collision sample budget exceeded")

        def stream() -> Iterator[Array]:
            yield self.start.copy()
            for i in range(1, count):
                yield self.start + delta * (i / count)
            yield self.goal.copy()

        return stream()


def plan(start: object, goal: object, config: Config, duration: float | None = None) -> Trajectory:
    q0, q1 = joints(start), joints(goal)
    delta = np.abs(q1 - q0)
    # max s' = 15/8; max |s''| = 10*sqrt(3)/3, u in [0,1].
    try:
        with np.errstate(over="raise", divide="raise", invalid="raise"):
            minimum = max(
                config.control_dt,
                float(np.max(1.875 * delta / config.velocity)),
                float(np.max(np.sqrt((10 * np.sqrt(3) / 3) * delta / config.acceleration))),
            )
    except FloatingPointError as exc:
        raise CommandError("Timing limits exceed the supported numeric range") from exc
    if duration is not None:
        duration = scalar(duration, "Duration")
    if duration is not None and duration < minimum:
        raise CommandError(f"Duration must be >= {minimum:.6f} seconds")
    q0.setflags(write=False)
    q1.setflags(write=False)
    return Trajectory(q0, q1, minimum if duration is None else float(duration))
