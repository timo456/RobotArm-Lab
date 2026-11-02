"""Transactional command validation and deterministic kinematic execution."""

import json
from pathlib import Path
from time import time

import numpy as np

from .config import Config
from .kinematics import pose_error, solve_ik
from .model import HOME, Array, CommandError, Pose
from .simulation import World
from .trajectory import Trajectory, plan
from .validation import scalar


class Controller:
    def __init__(self, world: World, config: Config, log: Path | None = None) -> None:
        self.world, self.config, self.log = world, config, log
        self.state = "IDLE"
        self.last_error = ""
        self.trajectory: Trajectory | None = None
        self.elapsed = 0.0
        self.velocity = np.zeros(6)
        self.acceleration = np.zeros(6)
        if log:
            log.parent.mkdir(parents=True, exist_ok=True)

    @property
    def q(self) -> Array:
        return self.world.get_q()

    def event(self, kind: str, **data: object) -> None:
        if self.log:
            try:
                with self.log.open("a", encoding="utf-8") as stream:
                    stream.write(
                        json.dumps(
                            {"time_unix": time(), "event": kind, "state": self.state, **data},
                            allow_nan=False,
                        )
                        + "\n"
                    )
            except OSError as exc:
                self.trajectory = None
                self.velocity[:] = 0
                self.acceleration[:] = 0
                self.state, self.last_error = "FAULT", f"Event log unavailable: {exc}"
                raise CommandError(self.last_error) from exc

    def validate_path(self, trajectory: Trajectory) -> None:
        for i, q in enumerate(trajectory.collision_samples(self.config.collision_joint_step)):
            hits = self.world.collisions(q, self.config.collision_margin)
            if hits:
                raise CommandError(
                    f"Collision clearance rejected at sample {i}: {hits[0].kind}, "
                    f"link {hits[0].link_a}, distance {hits[0].distance:.4f} m"
                )

    def move(self, goal: object, duration: float | None = None) -> Trajectory:
        try:
            if self.state == "RUNNING":
                raise CommandError("Busy: stop or wait before sending a new command")
            trajectory = plan(self.q, goal, self.config, duration)
            self.validate_path(trajectory)
        except (ValueError, TypeError) as exc:
            self.last_error = str(exc)
            self.event("rejected", reason=str(exc))
            raise CommandError(str(exc)) from exc
        self.trajectory, self.elapsed = trajectory, 0.0
        self.state, self.last_error = "RUNNING", ""
        self.event("accepted", goal=trajectory.goal.tolist(), duration=trajectory.duration)
        return trajectory

    def move_pose(self, target: Pose) -> Trajectory:
        try:
            if self.state == "RUNNING":
                raise CommandError("Busy: stop or wait before sending a new command")
            result = solve_ik(target, self.q, self.config)
            pe, re = pose_error(self.world.pose_at(result.q), target)
            if pe > self.config.ik_position_tolerance or re > self.config.ik_orientation_tolerance:
                raise CommandError("Independent simulator pose validation failed")
        except CommandError as exc:
            self.last_error = str(exc)
            self.event("ik_rejected", reason=str(exc))
            raise
        self.event(
            "ik_solved",
            position_error=pe,
            orientation_error=re,
            elapsed_ms=result.elapsed_ms,
        )
        return self.move(result.q)

    def step(self, dt: float | None = None) -> None:
        dt = scalar(self.config.control_dt if dt is None else dt, "Execution step")
        if dt <= 0 or dt > 0.05:
            raise CommandError("Execution step must be in (0, 0.05] seconds")
        if self.state != "RUNNING" or self.trajectory is None:
            return
        t = min(self.elapsed + dt, self.trajectory.duration)
        q, velocity, acceleration = self.trajectory.sample(t)
        # Recheck the whole incremental segment, including current pose: scene can change.
        try:
            self.validate_path(Trajectory(self.q, q, dt))
        except CommandError as exc:
            self.stop()
            self.state, self.last_error = "BLOCKED", str(exc)
            self.event("runtime_blocked", reason=str(exc))
            return
        self.world.set_q(q)
        self.velocity, self.acceleration, self.elapsed = velocity, acceleration, t
        if t >= self.trajectory.duration:
            self.state = "IDLE"
            self.velocity[:] = 0
            self.acceleration[:] = 0
            self.event("completed", q=self.q.tolist())

    def run_until_idle(self) -> None:
        while self.state == "RUNNING":
            self.step()
        if self.state == "BLOCKED":
            raise CommandError(self.last_error)

    def stop(self) -> None:
        """Immediate simulation freeze; deliberately not a physical braking controller."""
        self.trajectory = None
        self.velocity[:] = 0
        self.acceleration[:] = 0
        self.state = "STOPPED"
        self.event("stopped")

    def home(self) -> Trajectory:
        return self.move(HOME)

    def reset(self) -> None:
        """Explicit simulation reset: clear obstacles and place arm at home."""
        self.stop()
        self.world.reset_scene()
        self.state, self.last_error = "IDLE", ""
        self.elapsed = 0.0
        self.event("reset")
